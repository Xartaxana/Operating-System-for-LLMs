"""Battery for tools/critic_verdict_check.py (N3, docs/tasks/2026-07-21_validation-import.md).

Covers: valid verdict/*, invalid combinations, fence extraction (missing /
unclosed / duplicate blocks), broken/non-object JSON, per-field required
checks, non-ASCII data vs ASCII diagnostics, empty input, a large-text
boundary, non-UTF-8 input (utf-16 file, arbitrary invalid-UTF-8 bytes), and
an anti-drift check comparing tools/critic_verdict.schema.json against the
checker's hardcoded rules: required/enum AND the allOf/if/then cross-field
rules, mechanically derived from the schema file itself (CLAUDE.md R11:
scope ceiling = keys + battery + boundaries, no full regress).

Run: python -m pytest tools/test_critic_verdict_check.py -q
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import critic_verdict_check as cvc

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "tools" / "critic_verdict.schema.json"
CHECKER_PATH = REPO_ROOT / "tools" / "critic_verdict_check.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _wrap(obj, prefix="Findings go here.\n\n", suffix="\n"):
    return prefix + "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```" + suffix


def _base_fit():
    return {
        "verdict": "fit",
        "blockers": [],
        "class_completeness": "ось 3 покрыта, аналогов не найдено",
        "trail": {
            "read": ["tools/critic_verdict_check.py"],
            "reruns": [
                {
                    "command": "python -m pytest tools/test_critic_verdict_check.py -q",
                    "result": "42 passed",
                }
            ],
        },
    }


def _base_fit_with_fixes():
    obj = _base_fit()
    obj["verdict"] = "fit_with_fixes"
    obj["fixes"] = ["добавить тест на границу N"]
    return obj


def _base_blocker():
    obj = _base_fit()
    obj["verdict"] = "blocker"
    obj["blockers"] = ["критическая находка: race condition в X"]
    return obj


def _run_cli(args, input_text=None):
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)] + args,
        cwd=str(REPO_ROOT),
        input=input_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# valid verdicts (acceptance keys)
# ---------------------------------------------------------------------------


def test_valid_fit_empty_blockers():
    ok, errors, obj = cvc.check_text(_wrap(_base_fit()))
    assert ok, errors
    assert obj["verdict"] == "fit"


def test_valid_fit_with_fixes_nonempty_fixes():
    ok, errors, obj = cvc.check_text(_wrap(_base_fit_with_fixes()))
    assert ok, errors


def test_valid_blocker_nonempty_blockers():
    ok, errors, obj = cvc.check_text(_wrap(_base_blocker()))
    assert ok, errors


# ---------------------------------------------------------------------------
# verdict/blockers/fixes cross-field rules
# ---------------------------------------------------------------------------


def test_fit_with_fixes_missing_fixes_fails():
    obj = _base_fit_with_fixes()
    del obj["fixes"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("fixes" in e for e in errors)


def test_fit_with_fixes_empty_fixes_fails():
    obj = _base_fit_with_fixes()
    obj["fixes"] = []
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("fixes" in e for e in errors)


def test_blocker_with_empty_blockers_fails():
    obj = _base_blocker()
    obj["blockers"] = []
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_fit_with_nonempty_blockers_fails():
    obj = _base_fit()
    obj["blockers"] = ["not actually empty"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_verdict_outside_enum_fails():
    obj = _base_fit()
    obj["verdict"] = "meh"
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("verdict" in e for e in errors)


# ---------------------------------------------------------------------------
# fence extraction
# ---------------------------------------------------------------------------


def test_no_json_block_fails():
    ok, errors, _ = cvc.check_text("Just prose, no fenced block anywhere.")
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_two_blocks_uses_last():
    first = {"verdict": "meh"}  # malformed on purpose - must NOT be used
    second = _base_fit_with_fixes()
    text = (
        "Draft:\n```json\n"
        + json.dumps(first)
        + "\n```\n\nFinal:\n```json\n"
        + json.dumps(second)
        + "\n```\n"
    )
    ok, errors, obj = cvc.check_text(text)
    assert ok, errors
    assert obj["verdict"] == "fit_with_fixes"


def test_unclosed_fence_reports_no_block():
    text = "Findings.\n```json\n" + json.dumps(_base_fit())
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_broken_json_fails():
    text = "Findings.\n```json\n{not valid json,,,\n```\n"
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("invalid JSON" in e for e in errors)


def test_json_array_instead_of_object_fails():
    text = "Findings.\n```json\n[1, 2, 3]\n```\n"
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("not an object" in e for e in errors)


# ---------------------------------------------------------------------------
# per-field required checks (named field in diagnostic)
# ---------------------------------------------------------------------------


def test_missing_verdict_field():
    obj = _base_fit()
    del obj["verdict"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("verdict" in e for e in errors)


def test_missing_blockers_field():
    obj = _base_fit()
    del obj["blockers"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_missing_class_completeness_field():
    obj = _base_fit()
    del obj["class_completeness"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("class_completeness" in e for e in errors)


def test_missing_trail_field():
    obj = _base_fit()
    del obj["trail"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail" in e for e in errors)


def test_trail_without_read_fails():
    obj = _base_fit()
    del obj["trail"]["read"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail.read" in e for e in errors)


def test_trail_without_reruns_fails():
    obj = _base_fit()
    del obj["trail"]["reruns"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail.reruns" in e for e in errors)


def test_reruns_element_without_command_fails():
    obj = _base_fit()
    obj["trail"]["reruns"] = [{"result": "3 passed"}]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("command" in e for e in errors)


def test_reruns_element_without_result_fails():
    obj = _base_fit()
    obj["trail"]["reruns"] = [{"command": "pytest -q"}]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("result" in e for e in errors)


# ---------------------------------------------------------------------------
# ASCII diagnostics vs non-ASCII data; empty input; large input boundary
# ---------------------------------------------------------------------------


def test_cyrillic_data_is_valid_and_output_is_ascii():
    obj = _base_blocker()
    obj["blockers"] = ["Кириллический текст находки блокера"]
    obj["class_completeness"] = "ось 3 покрыта, ось 7 в очередь порта"
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert ok, errors

    result = _run_cli(["-"], input_text=_wrap(obj))
    assert result.returncode == 0
    assert result.stdout.strip().startswith("VERDICT OK:")
    result.stdout.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_diagnostics_are_ascii_even_with_cyrillic_input():
    obj = _base_fit()
    obj["blockers"] = ["Кириллический не-пустой blockers при fit"]
    result = _run_cli(["-"], input_text=_wrap(obj))
    assert result.returncode == 1
    result.stderr.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_empty_input_fails():
    ok, errors, _ = cvc.check_text("")
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_large_input_with_trailing_block_works():
    padding = "x" * 120_000
    text = padding + "\n\n" + _wrap(_base_fit_with_fixes())
    ok, errors, obj = cvc.check_text(text)
    assert ok, errors
    assert obj["verdict"] == "fit_with_fixes"


# ---------------------------------------------------------------------------
# non-UTF-8 input (fix #1, critic verdict t-259: file-open branch must not
# leak a raw traceback on decode failure — fail-closed with an ASCII line)
# ---------------------------------------------------------------------------


def test_cli_utf16_file_fails_clean_no_traceback(tmp_path):
    p = tmp_path / "verdict_utf16.txt"
    p.write_text(_wrap(_base_fit()), encoding="utf-16")
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in result.stderr
    result.stderr.encode("ascii")
    result.stdout.encode("ascii")


def test_cli_arbitrary_invalid_bytes_file_fails_clean_no_traceback(tmp_path):
    p = tmp_path / "verdict_garbage.bin"
    p.write_bytes(bytes([0xFF, 0xFE, 0x00, 0xD8, 0xFF, 0xFF, 0x80, 0x81] * 50))
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in result.stderr
    result.stderr.encode("ascii")
    result.stdout.encode("ascii")


def test_cli_stdin_invalid_bytes_fails_clean_no_traceback():
    # Same failure class as the file branch (D-0043: the class, not the
    # instance): invalid bytes on stdin. PYTHONIOENCODING pins the child's
    # stdin to strict utf-8 so the case is deterministic across locales
    # (default Windows locale may decode 0xFF permissively as cp1251).
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(CHECKER_PATH), "-"],
        cwd=str(REPO_ROOT),
        input=bytes([0xFF, 0xFE, 0x80, 0x81] * 20),
        capture_output=True,
        timeout=15,
        env=env,
    )
    assert result.returncode == 1
    stderr = result.stderr.decode("ascii")
    stdout = result.stdout.decode("ascii")
    assert "Traceback" not in stderr
    assert "Traceback" not in stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in stderr


# ---------------------------------------------------------------------------
# CLI contract (file path and stdin "-")
# ---------------------------------------------------------------------------


def test_cli_valid_file_exit_zero(tmp_path):
    p = tmp_path / "verdict.txt"
    p.write_text(_wrap(_base_fit()), encoding="utf-8")
    result = _run_cli([str(p)])
    assert result.returncode == 0
    assert "VERDICT OK: fit, blockers: 0, fixes: 0" in result.stdout


def test_cli_invalid_file_exit_one(tmp_path):
    p = tmp_path / "verdict.txt"
    obj = _base_fit()
    del obj["class_completeness"]
    p.write_text(_wrap(obj), encoding="utf-8")
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "INVALID VERDICT" in result.stderr
    assert "class_completeness" in result.stderr


def test_cli_stdin_dash_valid():
    result = _run_cli(["-"], input_text=_wrap(_base_blocker()))
    assert result.returncode == 0
    assert "VERDICT OK: blocker" in result.stdout


def test_cli_missing_argument_exit_one():
    result = _run_cli([])
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# anti-drift: schema.json required/enum sets vs checker's actual behavior
# ---------------------------------------------------------------------------


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_top_level_required_matches_checker_one_case_per_field():
    schema = _load_schema()
    required = schema["required"]
    for field in required:
        obj = _base_fit()
        del obj[field]
        ok, errors, _ = cvc.check_text(_wrap(obj))
        assert not ok, "schema requires %r but checker accepted its absence" % field
        assert any(field in e for e in errors), (
            "checker rejected missing %r but did not name it: %s" % (field, errors)
        )


def test_schema_trail_required_matches_checker_one_case_per_field():
    schema = _load_schema()
    trail_required = schema["properties"]["trail"]["required"]
    for field in trail_required:
        obj = _base_fit()
        del obj["trail"][field]
        ok, errors, _ = cvc.check_text(_wrap(obj))
        assert not ok, "schema requires trail.%r but checker accepted its absence" % field
        assert any(field in e for e in errors), (
            "checker rejected missing trail.%r but did not name it: %s" % (field, errors)
        )


def test_schema_verdict_enum_matches_checker_enum():
    schema = _load_schema()
    schema_enum = set(schema["properties"]["verdict"]["enum"])
    assert schema_enum == set(cvc.VERDICT_ENUM)


def test_schema_verdict_enum_each_value_accepted_one_case_per_value():
    schema = _load_schema()
    builders = {
        "fit": _base_fit,
        "fit_with_fixes": _base_fit_with_fixes,
        "blocker": _base_blocker,
    }
    for value in schema["properties"]["verdict"]["enum"]:
        assert value in builders, "no test fixture for schema enum value %r" % value
        ok, errors, obj = cvc.check_text(_wrap(builders[value]()))
        assert ok, errors
        assert obj["verdict"] == value


def test_schema_allof_cross_field_rules_matches_checker():
    """Derives cases from schema.json's allOf/if/then blocks (the
    fit->blockers-empty, blocker->blockers-nonempty, fit_with_fixes->fixes
    rules) instead of hardcoding them, so a future edit to the allOf shape
    that the checker does not mirror is caught here rather than drifting
    silently. For each (verdict, field) pair found in a then.properties
    with maxItems/minItems, and each then.required field, generates a
    negative (violates the derived constraint) and, where applicable, a
    positive mirror case and checks both against the checker."""
    schema = _load_schema()
    all_of = schema.get("allOf", [])
    assert all_of, "schema has no allOf cross-field rules to derive cases from"

    builders = {
        "fit": _base_fit,
        "fit_with_fixes": _base_fit_with_fixes,
        "blocker": _base_blocker,
    }

    checked_any = False
    for entry in all_of:
        const = entry["if"]["properties"]["verdict"]["const"]
        assert const in builders, "no test fixture for allOf verdict %r" % const
        then = entry.get("then", {})

        for field_name, field_schema in then.get("properties", {}).items():
            max_items = field_schema.get("maxItems")
            if max_items == 0:
                checked_any = True
                bad = dict(builders[const]())
                bad[field_name] = ["violates maxItems 0"]
                ok, errors, _ = cvc.check_text(_wrap(bad))
                assert not ok, (
                    "schema allOf(verdict=%r) caps %r at maxItems 0 but checker "
                    "accepted a non-empty value" % (const, field_name)
                )

                good = dict(builders[const]())
                good[field_name] = []
                ok, errors, _ = cvc.check_text(_wrap(good))
                assert ok, (
                    "schema allOf(verdict=%r) allows empty %r but checker "
                    "rejected it: %s" % (const, field_name, errors)
                )

            min_items = field_schema.get("minItems")
            if min_items and min_items >= 1:
                checked_any = True
                bad = dict(builders[const]())
                bad[field_name] = []
                ok, errors, _ = cvc.check_text(_wrap(bad))
                assert not ok, (
                    "schema allOf(verdict=%r) requires %r minItems %d but "
                    "checker accepted an empty value" % (const, field_name, min_items)
                )

                good = dict(builders[const]())
                good[field_name] = ["x"] * min_items
                ok, errors, _ = cvc.check_text(_wrap(good))
                assert ok, (
                    "schema allOf(verdict=%r) allows %r with %d item(s) but "
                    "checker rejected it: %s" % (const, field_name, min_items, errors)
                )

        for req_field in then.get("required", []):
            checked_any = True
            bad = dict(builders[const]())
            bad.pop(req_field, None)
            ok, errors, _ = cvc.check_text(_wrap(bad))
            assert not ok, (
                "schema allOf(verdict=%r) requires field %r but checker "
                "accepted its absence" % (const, req_field)
            )
            assert any(req_field in e for e in errors), (
                "checker rejected missing %r (verdict=%r) but did not name it: %s"
                % (req_field, const, errors)
            )

    assert checked_any, "no mechanically-derivable allOf case found in schema"
