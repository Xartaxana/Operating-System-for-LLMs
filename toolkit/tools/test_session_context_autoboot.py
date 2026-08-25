"""Tests for the AUTO-BOOT gating half of the Layer A hybrid mechanism:
extract_source()/should_emit_layer_a() -- WHEN the layer-A block fires,
as distinct from test_session_context_layer_a.py, which covers WHAT gets
emitted. Kept as its own file (the port's DoD names it as a new, separate
test module) rather than folded into test_session_context.py or
test_session_context_layer_a.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_context as sc  # noqa: E402


# ---- extract_source() ----


def test_extract_source_present_string():
    assert sc.extract_source({"source": "startup"}) == "startup"


def test_extract_source_missing_key_returns_none():
    assert sc.extract_source({}) is None


def test_extract_source_non_dict_payload_returns_none():
    assert sc.extract_source(None) is None
    assert sc.extract_source("not a dict") is None
    assert sc.extract_source(["startup"]) is None


def test_extract_source_empty_string_returns_none():
    assert sc.extract_source({"source": ""}) is None


def test_extract_source_non_string_value_returns_none():
    assert sc.extract_source({"source": 42}) is None
    assert sc.extract_source({"source": None}) is None


# ---- should_emit_layer_a() ----


def test_should_emit_layer_a_fires_on_startup():
    assert sc.should_emit_layer_a("startup") is True


def test_should_emit_layer_a_fires_on_clear():
    assert sc.should_emit_layer_a("clear") is True


def test_should_emit_layer_a_does_not_fire_on_resume():
    assert sc.should_emit_layer_a("resume") is False


def test_should_emit_layer_a_does_not_fire_on_compact():
    assert sc.should_emit_layer_a("compact") is False


def test_should_emit_layer_a_fires_on_none_fail_toward_booting():
    # None means "no source field at all" (extract_source's own
    # contract on a missing/non-dict/malformed payload) -- must still
    # fire rather than silently going quiet on an unrecognized shape.
    assert sc.should_emit_layer_a(None) is True


def test_should_emit_layer_a_fires_on_unrecognized_source_string():
    assert sc.should_emit_layer_a("some-future-harness-source") is True


# ---- main() end-to-end: the gate actually suppresses/allows the block ----


def _seed_minimal_repo(root: Path):
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    (root / "BOOT.md").write_text("1. Read README.md.\n", encoding="utf-8")
    (root / "README.md").write_text("hello world\n", encoding="utf-8")


class _FakeStdin:
    def __init__(self, text):
        self._text = text

    def isatty(self):
        return False

    @property
    def buffer(self):
        return self

    def read(self):
        return self._text.encode("utf-8")


def test_main_emits_layer_a_block_on_startup_source(tmp_path, monkeypatch, capsys):
    _seed_minimal_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdin('{"source": "startup"}'))
    code = sc.main(tmp_path)
    assert code == 0
    out = capsys.readouterr().out
    assert "BOOT LAYER A INJECTED" in out
    assert "END BOOT LAYER A:" in out


def test_main_suppresses_layer_a_block_on_resume_source(tmp_path, monkeypatch, capsys):
    _seed_minimal_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdin('{"source": "resume"}'))
    code = sc.main(tmp_path)
    assert code == 0
    out = capsys.readouterr().out
    assert "BOOT LAYER A INJECTED" not in out
    assert "END BOOT LAYER A:" not in out
    # The boot-lite context itself is unaffected by the gate.
    assert "NOW:" in out


def test_main_suppresses_layer_a_block_on_compact_source(tmp_path, monkeypatch, capsys):
    _seed_minimal_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdin('{"source": "compact"}'))
    code = sc.main(tmp_path)
    assert code == 0
    out = capsys.readouterr().out
    assert "BOOT LAYER A INJECTED" not in out


def test_main_emits_layer_a_block_with_no_stdin_payload_at_all(tmp_path, monkeypatch, capsys):
    # No payload -> extract_source() returns None -> fail-toward-booting.
    _seed_minimal_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", _FakeStdin(""))
    code = sc.main(tmp_path)
    assert code == 0
    out = capsys.readouterr().out
    assert "BOOT LAYER A INJECTED" in out
