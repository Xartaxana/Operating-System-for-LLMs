"""tools/-wide test isolation from boot-time / boot-adjacent live
artifacts -- фикс-батч калибровки №7 (2026-08-14), D-0043 class fix.

Class (docs/SIBLING_MAP.md, "Режимы отказа": неинъектируемый дефолт
пути тянется к боевому артефакту из тестового/подменённого контекста):
tools/spend_model.py::import_run_units() reads the module-level global
sm.RUN_UNITS_PATH when its own `path=` argument is None, and
tools/spend_model.py::rebuild() (called from ~19 sites across the
spend-analytics test modules) calls import_run_units(conn) with no
path override at all -- any test that calls rebuild() through a
module lacking its own isolation fixture silently reads/depends on the
REAL logs/run_units.jsonl the day it has content (it does, since
2026-08-14: 2 live run_start/run_end lines from session-handoff).

tools/test_spend_model.py and tools/test_spend_dashboard.py already
each carry their own module-local autouse fixture of this exact shape
(same fixture NAME, same effect) -- they are left untouched per this
batch's spec (not this dispatch's scope to remove/dedupe). This
conftest.py closes the class for every OTHER/future tools/ test module
in one place (R9): a module-local fixture of the SAME NAME shadows
this one for its own module (pytest fixture resolution -- closer scope
wins), so the two existing modules keep behaving exactly as before;
tools/test_spend_report.py (the missed third sibling that motivated
this batch) and any test module added later pick this one up for free.

Scope: PATH ISOLATION ONLY. This does not create, delete or modify
logs/run_units.jsonl -- it only redirects the module-level default a
test-context rebuild() would otherwise consult.
"""
from __future__ import annotations

import pytest

import spend_model as sm


@pytest.fixture(autouse=True)
def _isolate_run_units_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "RUN_UNITS_PATH", tmp_path / "run_units.jsonl")
