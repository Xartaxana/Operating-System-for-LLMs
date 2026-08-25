"""Tests for the AUTO-BOOT (D-0103) additions to tools/session_context.py
-- extract_source() / autoboot_lines() and their main() wiring. Built as a
sibling copy (session_context_autoboot.py) per D-0069 (a SessionStart hook
is a self-activating enforcement file); the Lead placed it onto the live
tools/session_context.py path at acceptance 2026-08-18 (boot restructure
C5), and this test now imports the LIVE module.

Run from the repo root: python -m pytest tools/test_session_context_autoboot.py -q
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent / "session_context.py"
_spec = importlib.util.spec_from_file_location("session_context", _MODULE_PATH)
sc = importlib.util.module_from_spec(_spec)
sys.modules["session_context"] = sc
_spec.loader.exec_module(sc)


class _FakeStdin:
    """Minimal stand-in for sys.stdin -- mirrors test_session_context.py's
    own _FakeStdin, used to drive main() end-to-end without touching the
    real process stdin."""

    def __init__(self, text, tty=False):
        self._text = text
        self._tty = tty

    def isatty(self):
        return self._tty

    def read(self):
        return self._text


def _seed_repo(tmp_path) -> Path:
    """Minimal repo shape build_context_lines()/main() need: an empty
    journal dir and an empty gateway dir are enough -- quota_lines()
    tolerates a missing config.yaml the same way test_session_context.py's
    own gateway-dir-missing tests rely on (fail-open path), and this
    module's own tests only ever assert on the AUTO-BOOT lines, never on
    the boot-lite quota content."""
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "gateway").mkdir(exist_ok=True)
    return tmp_path


# ==== extract_source (AK4) ==================================================


def test_extract_source_top_level_string():
    assert sc.extract_source({"source": "startup"}) == "startup"


def test_extract_source_missing_key_returns_none():
    assert sc.extract_source({}) is None


def test_extract_source_none_payload_returns_none():
    assert sc.extract_source(None) is None


def test_extract_source_non_dict_payload_returns_none():
    assert sc.extract_source("not a dict") is None
    assert sc.extract_source(["source", "startup"]) is None
    assert sc.extract_source(123) is None


def test_extract_source_empty_string_value_returns_none():
    assert sc.extract_source({"source": ""}) is None


def test_extract_source_non_string_value_returns_none():
    assert sc.extract_source({"source": 42}) is None
    assert sc.extract_source({"source": None}) is None


# ==== autoboot_lines (AK1/AK2/AK3) ==========================================


def test_autoboot_lines_startup_present():
    lines = sc.autoboot_lines("startup")
    assert lines
    assert lines == sc._AUTOBOOT_DIRECTIVE_LINES
    # AK11 sibling fix (found empirically while verifying the two-world
    # edit above on a post-posting copy -- this assertion embeds the OLD
    # world's full first-line wording, a hardcoded pin the spec's own
    # breaking-tests list (S7 point 4, "test_autoboot_lines_* НЕ
    # ломаются") missed; report note): only the "AUTO-BOOT (D-0103"
    # prefix is the byte-stable guarantee across both worlds (AK8) -- the
    # rest of the old sentence is old-world-only text.
    assert lines[0].startswith("AUTO-BOOT (D-0103")


def test_autoboot_lines_clear_present():
    lines = sc.autoboot_lines("clear")
    assert lines
    assert lines == sc._AUTOBOOT_DIRECTIVE_LINES


def test_autoboot_lines_resume_absent():
    assert sc.autoboot_lines("resume") == []


def test_autoboot_lines_compact_absent():
    assert sc.autoboot_lines("compact") == []


def test_autoboot_lines_none_fails_toward_boot():
    assert sc.autoboot_lines(None) == sc._AUTOBOOT_DIRECTIVE_LINES


def test_autoboot_lines_unrecognized_string_fails_toward_boot():
    assert sc.autoboot_lines("xyz") == sc._AUTOBOOT_DIRECTIVE_LINES


def test_autoboot_directive_block_is_ascii_and_exact():
    # Hard invariant: ASCII only, do not translate to Cyrillic.
    for line in sc._AUTOBOOT_DIRECTIVE_LINES:
        assert line.isascii()
    joined = "\n".join(sc._AUTOBOOT_DIRECTIVE_LINES)
    # AK11 (D-0103 HYBRID, docs/tasks/2026-08-25_autoboot-hybrid-spec.md):
    # two-world form. Discriminator is the presence of _LAYER_A_FILES --
    # absent in today's live module (pre-posting: old directive-only
    # text), present after the hybrid sibling lands (AK8: new text, Layer
    # A content printed below the directive instead of "go read it").
    if hasattr(sc, "_LAYER_A_FILES"):
        assert joined == (
            "AUTO-BOOT (D-0103, operator opted in): fresh session start -- the full boot runs now.\n"
            "  Layer A (orientation) is PRINTED BELOW, verbatim -- it is ALREADY in your context.\n"
            "  Do NOT open or re-read those five files: re-reading them is the double payment\n"
            "  this injection exists to remove.\n"
            "  The block ends with a line reporting how many files, lines and bytes were emitted.\n"
            "  If you do NOT see that closing line, the injection was TRUNCATED -- read the five\n"
            "  files listed in BOOT.md yourself, and tell the operator the block was cut.\n"
            "  A Layer A file shown as [missing: ...] was NOT printed -- read that one file yourself.\n"
            "  Layer B (state) is NOT printed -- read CURRENT_CONTEXT.md yourself now.\n"
            "  Then produce a Boot Report per PROCESS/BOOT_REPORT_PROTOCOL.md and STOP for work\n"
            "  authorization.\n"
            "  (Boot recovery is not work authorization -- BOOT_REPORT_PROTOCOL rule 4.\n"
            "  This directive fires on a fresh start only, not after resume/compact.)"
        )
    else:
        assert joined == (
            "AUTO-BOOT (D-0103, operator opted in): fresh session start -- run the full boot now.\n"
            "  Read the files listed in BOOT.md in order, then produce a Boot Report per\n"
            "  PROCESS/BOOT_REPORT_PROTOCOL.md and STOP for work authorization.\n"
            "  (Boot recovery is not work authorization -- BOOT_REPORT_PROTOCOL rule 4.\n"
            "  This directive fires on a fresh start only, not after resume/compact.)"
        )


# ==== end-to-end main() (AK5) ===============================================


def test_main_startup_shows_boot_lite_and_autoboot(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    fake = _FakeStdin(json.dumps({"source": "startup"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert any(l.startswith("NOW:") for l in out)
    assert any(l.startswith("AUTO-BOOT") for l in out)
    if hasattr(sc, "_LAYER_A_FILES"):
        # AK11 (D-0103 HYBRID): new world additionally injects the Layer A
        # content block right after the directive (AK7).
        assert any(l.startswith("--- BOOT LAYER A") for l in out)
    else:
        # R2-К5 (ФИКС 5 критика): the OLD-world branch carries its OWN
        # assertion, symmetric to test_autoboot_directive_block_is_ascii_
        # and_exact's own else -- a renamed _LAYER_A_FILES constant must
        # fail this test LOUDLY (block missing where expected), never
        # silently no-op past a bare `if hasattr(...)` with nothing on
        # the other side.
        assert not any(l.startswith("--- BOOT LAYER A") for l in out)


def test_main_compact_shows_boot_lite_but_not_autoboot(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    fake = _FakeStdin(json.dumps({"source": "compact"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert any(l.startswith("NOW:") for l in out)
    assert not any(l.startswith("AUTO-BOOT") for l in out)
    if hasattr(sc, "_LAYER_A_FILES"):
        assert not any(l.startswith("--- BOOT LAYER A") for l in out)
    else:
        # R2-К5: symmetric else (see the startup test's own comment) --
        # true in both worlds here (compact never fires autoboot at all),
        # but the STRUCTURE stays uniform so a class-wide check (B27)
        # can enforce "no bare hasattr guard without an else" mechanically.
        assert not any(l.startswith("--- BOOT LAYER A") for l in out)


def test_main_resume_shows_boot_lite_but_not_autoboot(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    fake = _FakeStdin(json.dumps({"source": "resume"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert any(l.startswith("NOW:") for l in out)
    assert not any(l.startswith("AUTO-BOOT") for l in out)
    if hasattr(sc, "_LAYER_A_FILES"):
        assert not any(l.startswith("--- BOOT LAYER A") for l in out)
    else:
        # R2-К5: symmetric else, same rationale as compact's own above.
        assert not any(l.startswith("--- BOOT LAYER A") for l in out)


def test_main_missing_source_still_shows_autoboot(tmp_path, capsys, monkeypatch):
    # No "source" key at all in the payload -- fail-toward-boot.
    root = _seed_repo(tmp_path)
    fake = _FakeStdin(json.dumps({"model": "claude-sonnet-5"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert any(l.startswith("AUTO-BOOT") for l in out)


# ==== directive survives MAX_LINES truncation ===============================


def test_autoboot_survives_when_boot_lite_context_fills_max_lines(
    tmp_path, capsys, monkeypatch
):
    # build_context_lines() itself truncates at MAX_LINES (25) -- this
    # proves the AUTO-BOOT block is printed OUTSIDE that cap, as a
    # separate step in main(), not folded into build_context_lines()'s
    # own truncated return value.
    root = _seed_repo(tmp_path)
    filler = [f"FILLER {i}" for i in range(sc.MAX_LINES)]
    assert len(filler) == sc.MAX_LINES
    # Двухмирная форма (посадка F-61 узла B): боевой путь main() идёт
    # через приватную _build_context_lines_and_pending_ack, если она
    # есть; публичная build_context_lines() — тестовый/standalone шов.
    if hasattr(sc, "_build_context_lines_and_pending_ack"):
        monkeypatch.setattr(
            sc,
            "_build_context_lines_and_pending_ack",
            lambda *a, **kw: (filler, (tmp_path, [], None)),
        )
    else:
        monkeypatch.setattr(sc, "build_context_lines", lambda *a, **kw: filler)
    fake = _FakeStdin(json.dumps({"source": "startup"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) > sc.MAX_LINES
    assert out[: sc.MAX_LINES] == filler
    assert any(l.startswith("AUTO-BOOT") for l in out[sc.MAX_LINES :])


# ==== fail-open: an exception in the autoboot path does not blank the hook =


# ==== B27 (R2-К5): no bare hasattr(sc, "_LAYER_A_FILES") guard =============


def test_b27_layer_a_files_hasattr_guards_carry_symmetric_else_assertion():
    """R2-К5 (ФИКС 5 критика): every `if hasattr(sc, "_LAYER_A_FILES")`
    guard in THIS test file must carry an else branch with its own
    assertion -- a bare guard would silently no-op (not fail) instead of
    detecting the class the fix names: renaming _LAYER_A_FILES in a
    landed-but-broken module must fail this suite LOUDLY, not vanish
    into an untaken `if`. A structural (AST) check, not a narrow
    per-test assertion, so a FUTURE guard added the same bare way is
    caught mechanically too (D-0043: fix the class).

    ПРИНЯТАЯ ГРАНИЦА (вердикт критика t-595, фикс 5): детектор узнаёт
    только форму `if hasattr(...)` как ЦЕЛОЕ условие. Составное условие
    (`if hasattr(...) and X`), `if not hasattr(...)` и вынос предиката в
    переменную остаются вне его. На момент посадки таких форм в файле
    нет; появление одной из них -- осознанный обход, а не случайность."""
    text = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    guards = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Call)
            and isinstance(test.func, ast.Name)
            and test.func.id == "hasattr"
            and len(test.args) == 2
            and isinstance(test.args[1], ast.Constant)
            and test.args[1].value == "_LAYER_A_FILES"
        ):
            guards.append(node)
    assert guards, "sanity: no hasattr(sc, '_LAYER_A_FILES') guard found at all -- detector is vacuous"
    for node in guards:
        assert node.orelse, f"guard at line {node.lineno} has no else branch (B27 class)"
        has_assert = any(isinstance(stmt, ast.Assert) for stmt in node.orelse)
        assert has_assert, f"guard at line {node.lineno}'s else branch carries no assertion (B27 class)"


def test_main_fail_open_when_extract_source_raises(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    fake = _FakeStdin(json.dumps({"source": "startup"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)

    def _boom(_payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(sc, "extract_source", _boom)
    code = sc.main(root)
    assert code == 0
    captured = capsys.readouterr()
    out = (captured.out + captured.err).strip().splitlines()
    # Двухмирная форма (посадка F-61 узла B, решение Lead по фиксу 1):
    # rc=0 и строка предупреждения; буферизация all-or-nothing
    # отбрасывает частичный контекст по замыслу (Р6а), требование
    # «any NOW:» снято.
    assert any(l.startswith("session-context warning:") for l in out)
    assert not any(l.startswith("AUTO-BOOT") for l in out)
