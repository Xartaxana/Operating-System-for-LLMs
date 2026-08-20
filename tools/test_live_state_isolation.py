"""tools/test_live_state_isolation.py -- META-PIN, узел C (ремедиация
калибровки №8, F1/F14,
docs/tasks/2026-08-20_calibration-8-remediation.md, узел C). A
SEPARATE file (узел C decision Р3: "не conftest, не расширение
существующего файла" -- a shared tools/conftest.py fixture would apply
to all 60+ tools/ test modules at once and risks shadowing the
EXISTING run_units isolation fixture that conftest.py already carries;
appending to an existing test file would bury this class's own
detector inside an unrelated module).

MOTIVE: a canonical `python -m pytest tools/ gateway/ -q` run is a
witness of R2 acceptance and runs in the BACKGROUND by default (R7) --
so a test that reads REAL repo state (a live ledger dir, a live
snapshot file, a live journal) and compares it before/after a
subprocess call it makes is vulnerable to ANY concurrent session's own
hook writes landing in that same before/after window. The diff then
reflects the OTHER session's legitimate activity, not this test's own
subject -- a false red on the torn path. Four instances of this class
were found and fixed in this same узел C batch (2026-08-20); this file
is the PERMANENT machine guard against a fifth appearing unnoticed.

CLASSES (D-0100 enumeration -- verdict per carrier, not prose):

  Class A -- a test in tools/test_*.py directly reads/compares a REAL,
  repo-relative state path (logs/.search-ledger/, .claude/
  critic_snapshot.json, logs/routing-log.jsonl, etc.) before and after
  a subprocess call it makes, with no env-var/cwd isolation seam
  covering that exact path. FOUR known instances, ALL FIXED by this
  узел C batch (2026-08-20):
    A1 tools/test_search_control_gate.py::test_ledger_dir_honoured_from_env_var_not_real_logs
       -- FIXED: runs a byte-pinned tmp-tree COPY of the gate; the
       copy's own REPO constant resolves entirely inside tmp_path, so
       the real ledger dir is structurally unreachable, not merely
       "observed unchanged".
    A2 tools/test_search_control_gate.py::test_ledger_dir_never_defaults_to_real_logs_directory
       -- FIXED (rewritten "form A", узел C decision Р6): now actually
       exercises the GATE's own default (SEARCH_CONTROL_GATE_LEDGER_DIR
       left genuinely unset), not the test harness's own convenience
       tmp-dir guard the original form accidentally tested instead.
    A3 tools/test_critic_snapshot.py::test_real_repo_snapshot_untouched_by_tmp_path_dispatch
       -- FIXED: the live .claude/critic_snapshot.json is no longer
       read at all; края (ii) ("cwd comes from payload") is proven
       positively with two DIFFERENT tmp cwds instead.
    A4 tools/test_hook_liveness_probe.py::test_live_run_of_all_cases_is_ok
       -- FIXED: asserts the ATTRIBUTED `live_state_leaked` (this
       probe's own isolation failing), not the raw `live_state_diff`
       (which legitimately includes concurrent ambient activity) --
       hook_liveness_probe.py itself already carried the attribution
       logic (Р6(а)/t-522, 2026-08-19); only this test's own assertion
       had not been updated to use it.
  test_signature_scan_no_unfixed_class_a_pattern_in_tools (below) is
  this class's own machine detector, re-verified on every canon run,
  not merely at fix time.

  Class B -- a test reads a LIVE PROJECT DOCUMENT (CLAUDE.md,
  docs/*.md, PROCESS/*.md, ...) for its DECLARED CONTENT (e.g.
  asserting a rule number, a byte budget, a section heading) rather
  than a mutable operational state artifact. VERDICT: OUT OF SCOPE for
  this dispatch -- explicit non-goal (узел C spec: "НЕ чинить класс B
  ... норма координации и очередь"; decision Р4: "класс B не чинить").
  Not enumerated by file name here: this dispatch's given/owns basket
  did not include that list, and inventing one without a verified
  source would itself be a D-0011 violation ("never invent project
  state"). The distinguishing property from class A, stated for the
  record: a live DOC's content does not change mid-test-run purely
  from another session's ORDINARY ambient tool activity the way an
  operational ledger/snapshot/journal does -- a doc read is vulnerable
  to a genuine concurrent EDIT of that doc, a much rarer and more
  visible event, not to routine background hook writes. Kept as a
  distinct class deliberately, not folded into class A's fix.

  Class C -- FACT, NARROWED (2026-08-20, batch t-543 follow-up;
  supersedes the "accepted via signature scan" claim this paragraph
  used to make for the whole class). MEASURED (critic-gate batch,
  reproduced): a semantically identical class-A violator -- the SAME
  before/after live-path comparison anti-pattern, written under
  DIFFERENT names, no literal occurrence of any _FORBIDDEN_SIGNATURES
  string -- is INVISIBLE to the scan (empty result `{}`); a positive
  control with the OLD literal name ("_real_ledger_snapshot") is still
  caught (`{'test_known_shape.py': ['_real_ledger_snapshot']}`). The
  scan below is therefore a LITERAL-STRING regression pin of the THREE
  specific signatures this batch removed (`_FORBIDDEN_SIGNATURES`,
  covering all four known A1-A4 carriers -- A1 and A2 share one
  signature) -- NOT a semantic detector of the underlying class: a
  future instance of the same before/after live-path anti-pattern,
  written under new names or through a new helper function, is NOT
  caught by this mechanism.
  test_signature_scan_no_unfixed_class_a_pattern_in_tools below still
  re-verifies these three literal strings on every run (regression
  protection for the four KNOWN carriers, re-verified rather than
  trusted as a static one-time fix); "class C" in the original sense of
  "any future semantically-similar violator, caught automatically"
  remains a coordination/queue norm -- the same standing disclaimer
  shape as class B above, not something this file mechanically
  guarantees.

NON-GOAL (узел C non-goals, this dispatch): this file never edits any
gate (search_control_gate.py / critic_snapshot.py /
hook_liveness_probe.py) -- byte-for-byte, per the dispatch spec; it
only reads tools/test_*.py source text.

Run from the repo root: python -m pytest tools/test_live_state_isolation.py -q
"""
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent

# Patterns whose LITERAL PRESENCE in a tools/test_*.py source file
# signals the class-A anti-pattern this узел C batch removed. Matched
# as plain substrings against the file's raw text -- deliberately not
# a Python-aware parse (robust, trivially auditable, and the exact
# shape that was actually removed -- see the module docstring's class
# A enumeration for which test each signature used to live in).
_FORBIDDEN_SIGNATURES = (
    "_real_ledger_snapshot",       # A1/A2's removed live-read helper (name)
    'live_state_diff"] == []',     # A4's removed raw-diff assertion
    "_REAL_SNAPSHOT.read_bytes()",  # A3's removed live-file read
)


def _scan_directory_for_forbidden_signatures(directory: Path, exclude_names=()) -> dict:
    """Returns {filename: [matched_signature, ...]} for every
    tools/test_*.py directly under *directory* (non-recursive -- every
    known carrier and every plausible future one lives directly in
    tools/, and a recursive walk would need its own exclusion list for
    pytest's own tmp trees) whose source text contains ANY of
    _FORBIDDEN_SIGNATURES. *exclude_names* skips file names that would
    otherwise self-match (this file's own docstring/constant, which
    necessarily NAMES the signatures it looks for)."""
    hits = {}
    for path in sorted(directory.glob("test_*.py")):
        if path.name in exclude_names:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        matched = [sig for sig in _FORBIDDEN_SIGNATURES if sig in text]
        if matched:
            hits[path.name] = matched
    return hits


def test_signature_scan_no_unfixed_class_a_pattern_in_tools():
    """Class A machine detector, and class C's NARROWED form (see
    module docstring, "Class C -- FACT, NARROWED"): a clean scan of
    every tools/test_*.py file re-verifies the four known class-A
    carriers were rewritten to no longer contain any of the three
    literal _FORBIDDEN_SIGNATURES strings, on THIS run and every future
    one -- a LITERAL-STRING regression pin, not a semantic class
    detector; it does NOT guarantee that no OTHER test file introduces
    the same before/after live-path anti-pattern under a different
    name (measured: a signature scan on a semantically identical
    violator under different names returns {} -- see module docstring
    for the exact measurement)."""
    hits = _scan_directory_for_forbidden_signatures(
        TOOLS_DIR, exclude_names={Path(__file__).name}
    )
    assert hits == {}, (
        "live-state-comparison anti-pattern (узел C, class A) found in: "
        f"{hits} -- see tools/test_live_state_isolation.py's module "
        "docstring for the fix direction (tmp-copy isolation / "
        "attributed live_state_leaked / dual-tmp-cwd positive proof)."
    )


def test_wd_red_half_signature_scan_catches_a_synthetic_violator(tmp_path):
    """W-D red half for THIS meta-pin (узел C DoD point 4: "мета-пин --
    образец-нарушитель на tmp-дереве -- обязан упасть"). A synthetic
    tools/test_*.py-shaped file, planted in a TMP directory (never the
    real tools/ tree -- command hygiene p.7(г), never corrupt a live
    artifact when a pure function's verdict proves the same thing),
    containing one forbidden signature must be CAUGHT by the exact
    same scan function the live pin above uses -- proves the detector
    actually detects, not merely that a clean tree passes vacuously."""
    violator = tmp_path / "test_synthetic_violator.py"
    violator.write_text(
        "def test_x():\n"
        "    before = _real_ledger_snapshot()\n"
        "    assert before == {}\n",
        encoding="utf-8",
    )
    hits = _scan_directory_for_forbidden_signatures(tmp_path)
    assert "test_synthetic_violator.py" in hits
    assert "_real_ledger_snapshot" in hits["test_synthetic_violator.py"]


def test_wd_red_half_signature_scan_clean_tmp_tree_is_empty(tmp_path):
    """Boundary companion (rule 6a): the SAME scan on a tmp tree
    containing only a CLEAN synthetic file (none of the forbidden
    signatures) must report no hits -- the detector does not flag
    unrelated content, only the exact removed anti-patterns."""
    clean = tmp_path / "test_synthetic_clean.py"
    clean.write_text(
        "def test_y():\n"
        "    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    hits = _scan_directory_for_forbidden_signatures(tmp_path)
    assert hits == {}


def test_scan_excludes_its_own_file_name_self_reference():
    """This meta-pin's own module docstring/constant necessarily NAMES
    the forbidden signatures (to document what they are) -- the
    exclude_names parameter must keep the scan from self-matching when
    pointed at the real tools/ dir, or the live pin above would always
    fail regardless of the other files' state."""
    hits = _scan_directory_for_forbidden_signatures(
        TOOLS_DIR, exclude_names={"test_live_state_isolation.py"}
    )
    assert "test_live_state_isolation.py" not in hits
