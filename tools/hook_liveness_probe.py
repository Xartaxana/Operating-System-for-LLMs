"""tools/hook_liveness_probe.py -- liveness probe for ALL 12 hook gates
registered in .claude/settings.json (t-385, designer draft + Lead forks,
2026-08-10). Extends the tools/enforcement_probe.py pattern (dynamic
composition, verified against the live source instead of a hardcoded
list -- see that file's own docstring) from the single pre-commit gate
to the whole hook family.

MOTIVE: several of these gates detect their OWN failure only by reading
their OWN trail (a sidecar file, a track record, a printed marker) --
"probe silence" and "nothing to report" are indistinguishable from the
OUTSIDE without an independent fact-trigger. This probe feeds each gate
a deliberately triggering stdin payload inside an isolated temporary
tree and asserts the expected trail. "Probe fed -> trail must exist" --
a gate's silence becomes distinguishable from "nothing happened".

SCOPE LIMITATION (read this before treating a clean run as "the gates
are wired correctly"): this probe proves the LIVENESS OF THE GATE'S
OWN CODE -- that tools/<gate>.py, invoked directly with a triggering
payload, produces the trail its own source promises. It does NOT prove
WIRING liveness: registration in .claude/settings.json, matcher
correctness, an active hooksPath, or that the harness actually invokes
this script on the events it claims to. Wiring is the zone of
tools/wiring_check.py and calibration check 26(a) -- a clean run of
THIS probe with a broken/unregistered hooksPath still reports every
case OK, because every case here invokes the script directly by path,
never through the harness's own hook dispatch. Composition coverage
(CASE-MISSING/STALE-CASE below) checks that every hook COMMAND named
in .claude/settings.json has a matching case and vice versa -- this is
a manifest-consistency check, not a wiring-liveness check either: it
never asserts the harness actually calls these commands on the events
it says it does.

NON-GOAL: no byte of any tools/<gate>.py is touched by this file (a
gate producing a wrong/missing trail is a live finding to report, never
silently patched here). .claude/settings.json is read-only.

WHY A DECLARATIVE CASES TABLE (mirrors enforcement_probe.py's own
"build from source, not from a remembered list" philosophy): each case
names its target script, the kind of trail it produces (a printed
response, a written artifact, or both), a short LITERAL anchor baked
into this probe (independent of any import), and -- where the gate
exposes one -- the NAME of a public constant/message string the case
also verifies is still a non-empty string via direct import (D-0043
"single source of truth": if the gate's own wording constant goes
empty or the import breaks, that is itself a finding, not something
this probe should paper over with its own copy of the string). A
broken import of a gate module is caught, printed as a finding
(informational, per the accepted design decision), and does NOT crash
the probe -- the case still runs on its baked literal anchor alone.

ISOLATION: every stateful case gets its OWN tempfile.mkdtemp() tree,
OUTSIDE the repo's own directory tree (never under D:\\Improving_AI\\
Operating-System-for-LLMs itself) -- session_id values carry the
"liveness-probe-" prefix so a stray artifact is unmistakably this
probe's, not a real session's. Stateful gates that could otherwise
collide (owns_gate's two cases, dod_gate vs main_gate) get DIFFERENT
temp trees AND different session_id values, per the accepted design.
The invoked subprocess itself always runs with cwd=<repo root> (the
same shape every registered hook command already uses, "python
tools/<name>.py" from the repo root) -- isolation from the LIVE repo
state is achieved through each gate's own env-var override seams
(SEARCH_CONTROL_GATE_LEDGER_DIR / SEARCH_CONTROL_GATE_SAMPLE_PATH) and
through the payload's own "cwd"/"file_path" JSON fields, which is
exactly how the gates already source their own state-file locations --
not by changing the OS-level working directory of the child process.

PRE/POST LIVE-STATE CHECK (accepted design decision Р8а): before and
after the whole case run, this probe fingerprints (exists, size,
mtime_ns, sha256) every real state path a gate could have touched had
isolation failed -- .claude/critic_snapshot.json, .claude/dod_track/
(recursively), logs/owns_registry.jsonl, logs/.search-ledger/
(recursively), logs/routing-log.jsonl, logs/posttooluse-schema-sample.json,
all under THIS repo's own root. Any difference -> LIVE-STATE-TOUCHED,
overall run is non-OK regardless of individual case verdicts -- a
passing case that quietly touched the live repo is a WORSE finding
than a case that plainly failed.

VERDICTS (per case): OK, DEAD (a trail was expected -- neither output
nor artifact appeared), MISMATCH (output/artifact appeared but the
anchor is missing, or the declared exit code does not match, or an
imported constant went empty), CRASH (an unhandled Python traceback
escaped the gate -- these gates are all documented fail-open; an
escaping traceback is itself the finding), HUNG (killed on timeout,
partial output reported), MISSING (the target script file does not
exist on disk). Composition-level findings: CASE-MISSING (a hook
command in .claude/settings.json has no matching case -- FAIL, per
accepted decision Р4а), STALE-CASE (a case names a script no hook
command in .claude/settings.json references), SETTINGS-UNREADABLE
(.claude/settings.json missing/unparsable -- cases still run, overall
result is non-OK), NO-CASES (the CASES table itself is empty -- a
defect of this probe, not of any gate).

EXIT CODE (accepted decision Р5б): 0 iff every case is OK AND
composition checks are clean AND settings.json was readable AND no
live-state drift was detected; 1 otherwise.

LIMITS (rule 6a CLAUDE.md -- boundary tests live in
tools/test_hook_liveness_probe.py): PER_CASE_TIMEOUT_SECONDS=20 is a
parameter of the runner (not a hardcoded literal at every call site),
overridable per case invocation; OUTPUT_EXCERPT_MAX_CHARS=500 truncates
any captured output/detail text embedded in a report line -- exactly
500 chars is kept whole, 501 is truncated with a trailing marker.
"""

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO, "tools")
SETTINGS_PATH = os.path.join(REPO, ".claude", "settings.json")

PER_CASE_TIMEOUT_SECONDS = 20
OUTPUT_EXCERPT_MAX_CHARS = 500

# --- verdict vocabulary --------------------------------------------------
OK = "OK"
DEAD = "DEAD"
MISMATCH = "MISMATCH"
CRASH = "CRASH"
HUNG = "HUNG"
MISSING = "MISSING"
CASE_MISSING = "CASE-MISSING"
STALE_CASE = "STALE-CASE"
LIVE_STATE_TOUCHED = "LIVE-STATE-TOUCHED"
NO_CASES = "NO-CASES"
SETTINGS_UNREADABLE = "SETTINGS-UNREADABLE"

_TRACEBACK_MARKER = "Traceback (most recent call last):"

# --- pre/post live-state fingerprint (Р8а) --------------------------------
_LIVE_STATE_TARGETS = (
    ("file", os.path.join(REPO, ".claude", "critic_snapshot.json")),
    ("dir", os.path.join(REPO, ".claude", "dod_track")),
    ("file", os.path.join(REPO, "logs", "owns_registry.jsonl")),
    ("dir", os.path.join(REPO, "logs", ".search-ledger")),
    ("file", os.path.join(REPO, "logs", "routing-log.jsonl")),
    ("file", os.path.join(REPO, "logs", "posttooluse-schema-sample.json")),
)


def _file_fingerprint(path):
    """(size, mtime_ns, sha256) of *path*, or None if it does not exist
    or cannot be read (a permission error is itself a fingerprint change
    relative to a readable "before" state, so it is not swallowed --
    None differs from any real tuple)."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    try:
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        digest = None
    return (st.st_size, st.st_mtime_ns, digest)


def snapshot_live_state() -> dict:
    """Fingerprints every real state path a gate could touch (see module
    docstring, "PRE/POST LIVE-STATE CHECK"). Directory targets are
    walked recursively; a missing directory contributes nothing (no key
    for it), same as a missing file contributing one key mapped to
    None -- both are DIFFERENT from "a file appeared there later" in the
    diff step (a new key appearing is itself a difference)."""
    snap = {}
    for kind, path in _LIVE_STATE_TARGETS:
        if kind == "file":
            snap[path] = _file_fingerprint(path)
        elif os.path.isdir(path):
            for dirpath, _dirnames, filenames in os.walk(path):
                for name in filenames:
                    fp = os.path.join(dirpath, name)
                    snap[fp] = _file_fingerprint(fp)
    return snap


def diff_live_state(before: dict, after: dict) -> list:
    """Sorted list of paths whose fingerprint changed OR that appeared/
    disappeared between the two snapshots."""
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


# --- output excerpt truncation (rule 6a boundary) -------------------------


def format_excerpt(s, max_chars: int = OUTPUT_EXCERPT_MAX_CHARS) -> str:
    """"" for None; *s* unchanged when len(s) <= max_chars (500 kept
    whole); truncated with a trailing marker when len(s) > max_chars
    (501 -> 500 chars + marker) -- see module docstring "LIMITS"."""
    if s is None:
        return ""
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + " \u2026[truncated]"


# --- gate module imports (for the const-non-empty sanity check) ----------

sys.path.insert(0, TOOLS_DIR)

_GATE_MODULE_NAMES = (
    "dispatch_gate",
    "owns_gate",
    "claim_control_gate",
    "search_control_gate",
    "negative_lint",
    "dod_gate",
    "main_gate",
    "journal_echo",
    "hygiene_gate",
    "dod_track",
    "critic_snapshot",
    "session_context",
)

_GATE_MODULES = {}
IMPORT_FINDINGS = []


def _import_gate_modules():
    """Imports every gate module once, catching failures individually --
    see module docstring, "WHY A DECLARATIVE CASES TABLE": a broken
    import is a finding (recorded to IMPORT_FINDINGS), never a crash of
    this probe. Idempotent -- safe to call more than once (tests call it
    fresh per-test via importlib.reload where needed)."""
    for name in _GATE_MODULE_NAMES:
        try:
            _GATE_MODULES[name] = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 -- deliberate catch-all, see docstring
            _GATE_MODULES[name] = None
            IMPORT_FINDINGS.append(
                f"import {name} failed: {type(exc).__name__}: {exc}"
            )


_import_gate_modules()


def _verify_const(module_name, const_name):
    """Returns "" when *const_name* on the (already-imported) module
    named *module_name* is a non-empty string; otherwise a short finding
    string describing why (module not imported / attribute missing /
    not a non-empty string). Never raises."""
    mod = _GATE_MODULES.get(module_name)
    if mod is None:
        return f"module {module_name} not importable"
    value = getattr(mod, const_name, None)
    if not isinstance(value, str) or not value:
        return f"{module_name}.{const_name} is empty/missing"
    return ""


# --- settings.json composition sverka (both directions) ------------------

import re  # noqa: E402 -- after sys.path manipulation, same style as sibling gates

_PY_TOOL_CMD_RE = re.compile(r"python\s+(tools/[A-Za-z0-9_./\\-]+\.py)")


def _read_text_best_effort(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return None


def load_settings_hook_commands(settings_path: str = SETTINGS_PATH):
    """Returns (event_name, command) pairs for every command hook found
    in *settings_path*'s "hooks" object, or None if the file is missing/
    unparsable (SETTINGS-UNREADABLE, see module docstring)."""
    text = _read_text_best_effort(settings_path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return []
    pairs = []
    for event_name, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for h in entry.get("hooks", []) or []:
                if isinstance(h, dict) and isinstance(h.get("command"), str):
                    pairs.append((event_name, h["command"]))
    return pairs


def classify_settings_commands(pairs):
    """Splits (event, command) pairs into (referenced_scripts: set of
    "tools/<name>.py", info_lines: list of str) -- a non-python-tool
    command is informational, never a failure (module docstring, WHY A
    DECLARATIVE CASES TABLE / spec: "не-python хуки -- информационная
    строка")."""
    scripts = set()
    info_lines = []
    for event_name, cmd in pairs:
        m = _PY_TOOL_CMD_RE.search(cmd)
        if m:
            scripts.add(m.group(1).replace("\\", "/"))
        else:
            info_lines.append(f'{event_name}: non-python hook command (informational): "{cmd}"')
    return scripts, info_lines


# --- subprocess case runner ------------------------------------------------


def run_subprocess_case(script_rel: str, payload: dict, env_overrides: dict = None,
                         timeout: int = PER_CASE_TIMEOUT_SECONDS) -> dict:
    """Invokes `python <repo>/<script_rel>` with *payload* fed as raw
    UTF-8 bytes on stdin (no text=True -- see module docstring/CLAUDE.md
    command hygiene: the real harness feeds raw bytes, not a text
    stream), cwd=<repo root> (the same shape every registered hook
    command already uses), env = os.environ copied + *env_overrides*.
    Returns a dict: {"missing": True} if the script file does not exist
    (no subprocess launched); {"hung": True, "stdout":..., "stderr":...}
    on timeout (subprocess.run already kills the child and returns
    whatever partial output it collected); otherwise
    {"returncode":..., "stdout":..., "stderr":...}.

    *script_rel* is normally repo-relative ("tools/<name>.py", the
    shape every real case in CASES uses); an ALREADY-ABSOLUTE path
    (Windows drive-letter form, used by this file's own test suite for
    synthetic scripts living under pytest's tmp_path -- which may sit
    on a DIFFERENT drive than REPO, making os.path.relpath raise) is
    used as-is, never joined with REPO -- naive `os.path.join(REPO,
    *script_rel.split("/"))` on a split absolute path silently produces
    a WRONG relative path on Windows (splitting "C:/x/y.py" loses its
    drive-absoluteness the moment the leading "C:" segment is rejoined
    without its trailing separator)."""
    if os.path.isabs(script_rel):
        script_path = script_rel
    else:
        script_path = os.path.join(REPO, *script_rel.split("/"))
    if not os.path.isfile(script_path):
        return {"missing": True}

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    input_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            input=input_bytes,
            capture_output=True,
            cwd=REPO,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "hung": True,
            "stdout": (exc.stdout or b"").decode("utf-8", errors="replace"),
            "stderr": (exc.stderr or b"").decode("utf-8", errors="replace"),
        }
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
    }


def _looks_like_traceback(text: str) -> bool:
    return _TRACEBACK_MARKER in (text or "")


def check_response(result: dict, expected_exit, anchors=(), forbidden=()) -> tuple:
    """Verdict logic for a "response" trail -- see module docstring,
    "VERDICTS". Returns (verdict, detail)."""
    if result.get("missing"):
        return MISSING, "script file not found"
    if result.get("hung"):
        return HUNG, format_excerpt("HUNG -- partial stdout=%r stderr=%r" % (
            result.get("stdout", ""), result.get("stderr", "")))

    out = result.get("stdout", "")
    err = result.get("stderr", "")
    combined = out + err

    if _looks_like_traceback(out) or _looks_like_traceback(err):
        return CRASH, format_excerpt(combined)

    if not out.strip() and not err.strip():
        return DEAD, "no output at all (a trail was expected)"

    reasons = []
    rc = result.get("returncode")
    if expected_exit is not None and rc != expected_exit:
        reasons.append(f"exit {rc} != expected {expected_exit}")
    for anchor in anchors:
        if anchor not in combined:
            reasons.append(f"anchor missing: {anchor!r}")
    for bad in forbidden:
        if bad in combined:
            reasons.append(f"forbidden substring present: {bad!r}")

    if reasons:
        return MISMATCH, format_excerpt("; ".join(reasons) + " | output: " + combined)
    return OK, format_excerpt(combined)


def check_artifact_only(result: dict, expected_exit, artifact_ok: bool, artifact_detail: str) -> tuple:
    """Verdict logic for a pure "artifact" trail (kind=="artifact") --
    empty stdout/stderr is the documented NORM here (dod_track.py's own
    contract), so silence alone is never DEAD by itself; the artifact's
    own presence/content is the trail."""
    if result.get("missing"):
        return MISSING, "script file not found"
    if result.get("hung"):
        return HUNG, format_excerpt("HUNG -- partial stdout=%r stderr=%r" % (
            result.get("stdout", ""), result.get("stderr", "")))

    out = result.get("stdout", "")
    err = result.get("stderr", "")
    if _looks_like_traceback(out) or _looks_like_traceback(err):
        return CRASH, format_excerpt(out + err)

    rc = result.get("returncode")
    if expected_exit is not None and rc != expected_exit:
        return MISMATCH, f"exit {rc} != expected {expected_exit}"

    if not artifact_ok:
        return DEAD, format_excerpt(artifact_detail)
    return OK, format_excerpt(artifact_detail)


def check_response_and_artifact(result: dict, expected_exit, anchors, forbidden,
                                 artifact_ok: bool, artifact_detail: str) -> tuple:
    """kind=="response+artifact": both the printed trail AND the on-disk
    trail are required. The response check runs first (missing/hung/
    crash there wins outright); if the response is OK, a missing/wrong
    artifact downgrades the verdict to MISMATCH (we DID get a trail --
    a partial one -- so DEAD would understate what happened)."""
    verdict, detail = check_response(result, expected_exit, anchors, forbidden)
    if verdict != OK:
        return verdict, detail
    if not artifact_ok:
        return MISMATCH, f"{detail} | artifact check failed: {format_excerpt(artifact_detail)}"
    return OK, f"{detail} | artifact: {format_excerpt(artifact_detail)}"


# --- individual case builders ----------------------------------------------
# Each _case_N_* function returns a dict: {"payload":..., "env": {...}|None}.
# Called fresh at RUN time (never at import time) so every invocation gets
# its own tempfile.mkdtemp() tree -- see module docstring, "ISOLATION".

_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _mkdtemp(label: str) -> str:
    return tempfile.mkdtemp(prefix=f"hook-liveness-probe-{label}-")


def _fwd(path: str) -> str:
    return path.replace("\\", "/")


def _case_1_dispatch_gate():
    tmp = _mkdtemp("dispatch-gate")
    payload = {
        "tool_name": "Task",
        "cwd": tmp,
        "session_id": "liveness-probe-dispatch",
        "tool_input": {
            "subagent_type": "builder",
            "description": "sonnet: quick fix",
            "prompt": (
                "Please implement the quick fix and merge it into main "
                "without delay, thanks."
            ),
        },
    }
    return {"payload": payload, "env": None, "extra": {"tmp": tmp}}


def _case_2_owns_gate_artifact():
    tmp = _mkdtemp("owns-gate")
    owns_path = _fwd(os.path.join(tmp, "artifact_owned_file.py"))
    payload = {
        "tool_name": "Task",
        "cwd": tmp,
        "session_id": "liveness-probe-owns-2",
        "tool_input": {
            "subagent_type": "builder",
            "description": "sonnet: probe",
            "prompt": (
                "Реализуй пробную фичу.\n\n"
                f"owns (ABSOLUTE write paths): {owns_path}\n"
            ),
        },
    }
    return {"payload": payload, "env": None, "extra": {"tmp": tmp, "owns_path": owns_path}}


def _case_2a_owns_gate_overlap():
    tmp = _mkdtemp("owns-gate-overlap")
    owns_path = _fwd(os.path.join(tmp, "shared_owned_file.py"))
    owns_gate_mod = _GATE_MODULES.get("owns_gate")

    registry_path = Path(tmp) / "logs" / "owns_registry.jsonl"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = now.strftime(_TS_FORMAT)
    prior = {
        "ts": ts,
        "session_key": "liveness-probe-owns-2a-prior",
        "cwd": tmp,
        "description": "prior probe write",
        "owns": [owns_path],
    }
    registry_path.write_text(json.dumps(prior, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = {
        "tool_name": "Task",
        "cwd": tmp,
        "session_id": "liveness-probe-owns-2a-second",
        "tool_input": {
            "subagent_type": "builder",
            "description": "sonnet: probe overlap",
            "prompt": (
                "Реализуй вторую пробную фичу.\n\n"
                f"owns (ABSOLUTE write paths): {owns_path}\n"
            ),
        },
    }
    return {
        "payload": payload, "env": None,
        "extra": {"tmp": tmp, "owns_path": owns_path, "owns_gate_mod": owns_gate_mod},
    }


def _case_3_claim_control_gate():
    tmp = _mkdtemp("claim-control")
    ledger_dir = os.path.join(tmp, "ledger")
    payload = {
        "tool_name": "Edit",
        "session_id": "liveness-probe-claim",
        "tool_input": {
            "file_path": "docs/probe_liveness_claim.md",
            "new_string": (
                "PROBE_TARGET_TOKEN.md does not exist anywhere in this "
                "repository."
            ),
        },
    }
    return {
        "payload": payload,
        "env": {"SEARCH_CONTROL_GATE_LEDGER_DIR": ledger_dir},
        "extra": {"tmp": tmp, "ledger_dir": ledger_dir},
    }


def _case_4_search_control_gate():
    tmp = _mkdtemp("search-control")
    ledger_dir = os.path.join(tmp, "ledger")
    sample_path = os.path.join(tmp, "posttooluse-schema-sample.json")
    session_id = "liveness-probe-search"
    payload = {
        "tool_name": "Grep",
        "session_id": session_id,
        "tool_input": {"pattern": "PROBE_LIVENESS_PATTERN_XYZ"},
        "tool_response": "",
    }
    return {
        "payload": payload,
        "env": {
            "SEARCH_CONTROL_GATE_LEDGER_DIR": ledger_dir,
            "SEARCH_CONTROL_GATE_SAMPLE_PATH": sample_path,
        },
        "extra": {"tmp": tmp, "ledger_dir": ledger_dir, "session_id": session_id},
    }


def _case_5_negative_lint():
    payload = {
        "tool_name": "Task",
        "tool_response": (
            "Проверил репозиторий: файл PROBE_MISSING_MARKER.md не найден."
        ),
    }
    return {"payload": payload, "env": None, "extra": {}}


def _case_6_dod_gate():
    tmp = _mkdtemp("dod-gate")
    session_id = "liveness-probe-dodgate"
    agent_id = "liveness-probe-dodgate-agent"
    track_path = Path(tmp) / ".claude" / "dod_track" / f"{session_id}.json"
    track_path.parent.mkdir(parents=True, exist_ok=True)
    file_path = _fwd(os.path.join(tmp, "probe_target.py"))
    track = {
        "edits": [
            {
                "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "tool_name": "Edit",
                "agent_id": agent_id,
                "file_path": file_path,
            }
        ],
        "runs": [],
        "gate_state": {"consecutive_blocks": 0, "per_agent": {}},
    }
    track_path.write_text(json.dumps(track, ensure_ascii=False), encoding="utf-8")

    payload = {
        "session_id": session_id,
        "cwd": tmp,
        "agent_id": agent_id,
        "hook_event_name": "SubagentStop",
    }
    return {
        "payload": payload, "env": None,
        "extra": {"tmp": tmp, "session_id": session_id, "track_path": str(track_path)},
    }


def _case_7_main_gate():
    tmp = _mkdtemp("main-gate")
    session_id = "liveness-probe-maingate"
    track_path = Path(tmp) / ".claude" / "dod_track" / f"{session_id}.json"
    track_path.parent.mkdir(parents=True, exist_ok=True)
    file_path = _fwd(os.path.join(tmp, "main_probe.py"))
    track = {
        "edits": [
            {
                "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "tool_name": "Edit",
                "agent_id": None,
                "file_path": file_path,
            }
        ],
        "runs": [],
        "main_gate_state": {"consecutive_blocks": 0},
    }
    track_path.write_text(json.dumps(track, ensure_ascii=False), encoding="utf-8")
    # Deliberately NOT creating <tmp>/logs/routing-log.jsonl -- see module
    # docstring / spec case 7: keeps the empty-journal warning branch out
    # of this case's scope.

    payload = {
        "session_id": session_id,
        "cwd": tmp,
        "hook_event_name": "Stop",
    }
    return {
        "payload": payload, "env": None,
        "extra": {"tmp": tmp, "session_id": session_id, "track_path": str(track_path)},
    }


def _case_8_journal_echo():
    tmp = _mkdtemp("journal-echo")
    journal_path = os.path.join(tmp, "logs", "routing-log.jsonl")
    os.makedirs(os.path.dirname(journal_path), exist_ok=True)
    with open(journal_path, "w", encoding="utf-8") as fh:
        fh.write("this is not a json line at all\n")

    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": journal_path},
    }
    return {"payload": payload, "env": None, "extra": {"tmp": tmp}}


def _case_9_dod_track():
    tmp = _mkdtemp("dod-track")
    session_id = "liveness-probe-dodtrack"
    file_path = _fwd(os.path.join(tmp, "probe_edit.py"))
    payload = {
        "tool_name": "Edit",
        "session_id": session_id,
        "cwd": tmp,
        "tool_input": {"file_path": file_path},
    }
    track_path = Path(tmp) / ".claude" / "dod_track" / f"{session_id}.json"
    return {
        "payload": payload, "env": None,
        "extra": {"tmp": tmp, "track_path": str(track_path), "file_path": file_path},
    }


def _case_10_critic_snapshot():
    tmp = _mkdtemp("critic-snapshot")
    # A non-empty tiny tree -- not required for correctness, but keeps
    # the snapshot's files_count meaningfully non-zero.
    (Path(tmp) / "probe_file_a.txt").write_text("probe content a\n", encoding="utf-8")

    payload = {
        "tool_name": "Task",
        "cwd": tmp,
        "tool_input": {"subagent_type": "critic"},
    }
    snap_path = Path(tmp) / ".claude" / "critic_snapshot.json"
    return {"payload": payload, "env": None, "extra": {"tmp": tmp, "snap_path": str(snap_path)}}


def _case_11_hygiene_gate():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo probe_marker >> logs/routing-log.jsonl"},
    }
    return {"payload": payload, "env": None, "extra": {}}


def _case_12_session_context():
    tmp = _mkdtemp("session-context")
    return {"payload": None, "env": None, "extra": {"tmp": tmp}}


# --- artifact checkers ------------------------------------------------


def _check_owns_registry_artifact(extra: dict) -> tuple:
    tmp = extra["tmp"]
    owns_path = extra["owns_path"]
    registry_path = Path(tmp) / "logs" / "owns_registry.jsonl"
    if not registry_path.exists():
        return False, f"{registry_path} does not exist"
    lines = [ln for ln in registry_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return False, f"{registry_path} is empty"
    try:
        last = json.loads(lines[-1])
    except Exception as exc:
        return False, f"last registry line is not valid JSON: {exc}"
    owns_gate_mod = _GATE_MODULES.get("owns_gate")
    owns_list = last.get("owns") or []
    if owns_gate_mod is not None:
        match = any(owns_gate_mod.normalize_path(p) == owns_gate_mod.normalize_path(owns_path)
                    for p in owns_list)
    else:
        match = owns_path in owns_list
    if not match:
        return False, f"registered owns {owns_list!r} does not include {owns_path!r}"
    return True, f"registered: {owns_list!r}"


def _check_search_ledger_artifact(extra: dict) -> tuple:
    ledger_dir = extra["ledger_dir"]
    session_id = extra["session_id"]
    candidates = [
        Path(ledger_dir) / f"{session_id}.jsonl",
        Path(ledger_dir) / "unknown.jsonl",
    ]
    for path in candidates:
        if path.exists() and path.read_text(encoding="utf-8").strip():
            return True, f"{path} non-empty"
    return False, f"no non-empty ledger file among {candidates}"


def _check_dod_gate_artifact(extra: dict) -> tuple:
    track_path = Path(extra["track_path"])
    if not track_path.exists():
        return False, f"{track_path} does not exist"
    try:
        data = json.loads(track_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"track file is not valid JSON: {exc}"
    gate_log = data.get("gate_log") or []
    if not gate_log or gate_log[-1].get("action") != "blocked":
        return False, f"gate_log tail is not a 'blocked' entry: {gate_log!r}"
    return True, f"gate_log tail: {gate_log[-1]!r}"


def _check_main_gate_artifact(extra: dict) -> tuple:
    track_path = Path(extra["track_path"])
    if not track_path.exists():
        return False, f"{track_path} does not exist"
    try:
        data = json.loads(track_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"track file is not valid JSON: {exc}"
    consecutive = (data.get("main_gate_state") or {}).get("consecutive_blocks")
    if consecutive != 1:
        return False, f"main_gate_state.consecutive_blocks = {consecutive!r}, expected 1"
    return True, "main_gate_state.consecutive_blocks == 1"


def _check_dod_track_artifact(extra: dict) -> tuple:
    track_path = Path(extra["track_path"])
    if not track_path.exists():
        return False, f"{track_path} does not exist"
    try:
        data = json.loads(track_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"track file is not valid JSON: {exc}"
    edits = data.get("edits") or []
    if not edits:
        return False, "edits list is empty"
    first = edits[0]
    if first.get("tool_name") != "Edit" or first.get("file_path") != extra["file_path"]:
        return False, f"unexpected edits[0]: {first!r}"
    return True, f"edits[0]: {first!r}"


def _check_critic_snapshot_artifact(extra: dict) -> tuple:
    snap_path = Path(extra["snap_path"])
    if not snap_path.exists():
        return False, f"{snap_path} does not exist"
    try:
        data = json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"snapshot is not valid JSON: {exc}"
    if "error" in data:
        return False, f"snapshot is a FAILURE document: {data!r}"
    if not isinstance(data.get("tree_hash"), str) or not data["tree_hash"]:
        return False, f"tree_hash missing/empty: {data!r}"
    if not isinstance(data.get("files_count"), int):
        return False, f"files_count missing/not int: {data!r}"
    return True, f"tree_hash={data['tree_hash'][:12]}... files_count={data['files_count']}"


# --- CASES table ------------------------------------------------------

CASES = [
    {
        "name": "1-dispatch_gate-block-no-dod",
        "script": "tools/dispatch_gate.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_1_dispatch_gate,
        "expected_exit": 2,
        "anchors": ("\u0431\u0435\u0437 DoD \u043d\u0435 \u0443\u0445\u043e\u0434\u0438\u0442",),
        "const_ref": ("dispatch_gate", "BLOCK_MESSAGE_NO_DOD"),
    },
    {
        "name": "2-owns_gate-artifact-registration",
        "script": "tools/owns_gate.py",
        "kind": "artifact",
        "isolation": "subprocess",
        "build": _case_2_owns_gate_artifact,
        "expected_exit": 0,
        "artifact_check": _check_owns_registry_artifact,
    },
    {
        "name": "2a-owns_gate-overlap-warn",
        "script": "tools/owns_gate.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_2a_owns_gate_overlap,
        "expected_exit": 0,
        "anchors": ("OWNS OVERLAP (warn):",),
    },
    {
        "name": "3-claim_control_gate-negative-claim-warn",
        "script": "tools/claim_control_gate.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_3_claim_control_gate,
        "expected_exit": 0,
        "anchors": (
            "Negative claim about to be written without a matching "
            "search/read this session (rule 6, command hygiene)",
        ),
        "const_ref": ("claim_control_gate", "MSG_TEMPLATE"),
    },
    {
        "name": "4-search_control_gate-empty-search-warn",
        "script": "tools/search_control_gate.py",
        "kind": "response+artifact",
        "isolation": "subprocess",
        "build": _case_4_search_control_gate,
        "expected_exit": 0,
        "anchors": ("Search returned nothing. Rule 6",),
        "const_ref": ("search_control_gate", "MSG"),
        "artifact_check": _check_search_ledger_artifact,
    },
    {
        "name": "5-negative_lint-warn",
        "script": "tools/negative_lint.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_5_negative_lint,
        "expected_exit": 0,
        "anchors": ("NEGATIVE LINT:",),
        "const_ref": ("negative_lint", "WARN_PREFIX_TEMPLATE"),
    },
    {
        "name": "6-dod_gate-block",
        "script": "tools/dod_gate.py",
        "kind": "response+artifact",
        "isolation": "subprocess",
        "build": _case_6_dod_gate,
        "expected_exit": 2,
        "anchors": ("\u0421\u0434\u0430\u0447\u0430 \u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u0430",),
        "const_ref": ("dod_gate", "BLOCK_MESSAGE"),
        "artifact_check": _check_dod_gate_artifact,
    },
    {
        "name": "7-main_gate-block",
        "script": "tools/main_gate.py",
        "kind": "response+artifact",
        "isolation": "subprocess",
        "build": _case_7_main_gate,
        "expected_exit": 2,
        "anchors": ("\u0421\u0434\u0430\u0447\u0430 main-\u0445\u043e\u0434\u0430 \u0437\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u0430",),
        "const_ref": ("main_gate", "BLOCK_MESSAGE"),
        "artifact_check": _check_main_gate_artifact,
    },
    {
        "name": "8-journal_echo-broken-json",
        "script": "tools/journal_echo.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_8_journal_echo,
        "expected_exit": 0,
        "anchors": ("JOURNAL ECHO:",),
    },
    {
        "name": "9-dod_track-artifact-silent",
        "script": "tools/dod_track.py",
        "kind": "artifact",
        "isolation": "subprocess",
        "build": _case_9_dod_track,
        "expected_exit": 0,
        "artifact_check": _check_dod_track_artifact,
    },
    {
        "name": "10-critic_snapshot-artifact",
        "script": "tools/critic_snapshot.py",
        "kind": "artifact",
        "isolation": "subprocess",
        "build": _case_10_critic_snapshot,
        "expected_exit": 0,
        "artifact_check": _check_critic_snapshot_artifact,
    },
    {
        "name": "11-hygiene_gate-journal-bypass-deny",
        "script": "tools/hygiene_gate.py",
        "kind": "response",
        "isolation": "subprocess",
        "build": _case_11_hygiene_gate,
        "expected_exit": 0,
        "anchors": (
            "\u0436\u0443\u0440\u043d\u0430\u043b\u044c\u043d\u044b\u0435 \u0437\u0430\u043f\u0438\u0441\u0438 \u2014 \u0442\u043e\u043b\u044c\u043a\u043e Edit/Write",
            '"permissionDecision": "deny"',
        ),
        "const_ref": ("hygiene_gate", "MSG_JOURNAL_BLOCK"),
    },
    {
        "name": "12-session_context-import-only",
        "script": "tools/session_context.py",
        "kind": "response",
        "isolation": "import",
        "build": _case_12_session_context,
        "expected_exit": None,
    },
]


# --- per-case execution -------------------------------------------------


def run_case(case: dict) -> dict:
    built = case["build"]()
    payload = built["payload"]
    env = built.get("env")
    extra = built.get("extra") or {}

    finding = ""
    const_ref = case.get("const_ref")
    if const_ref:
        finding = _verify_const(*const_ref)

    if case["isolation"] == "import":
        verdict, detail = _run_import_case(case, extra)
    else:
        result = run_subprocess_case(case["script"], payload, env)
        kind = case["kind"]
        expected_exit = case.get("expected_exit")
        anchors = case.get("anchors", ())
        if kind == "response":
            verdict, detail = check_response(result, expected_exit, anchors)
        elif kind == "artifact":
            artifact_check = case["artifact_check"]
            artifact_ok, artifact_detail = artifact_check(extra)
            verdict, detail = check_artifact_only(result, expected_exit, artifact_ok, artifact_detail)
        elif kind == "response+artifact":
            artifact_check = case["artifact_check"]
            artifact_ok, artifact_detail = artifact_check(extra)
            verdict, detail = check_response_and_artifact(
                result, expected_exit, anchors, (), artifact_ok, artifact_detail)
        else:
            verdict, detail = MISMATCH, f"unknown case kind: {kind!r}"

    if finding and verdict == OK:
        verdict = MISMATCH
    if finding:
        detail = f"{detail} | const-check: {finding}" if detail else f"const-check: {finding}"

    return {
        "name": case["name"],
        "script": case["script"],
        "verdict": verdict,
        "detail": format_excerpt(detail),
        "tmp": extra.get("tmp"),
    }


def _run_import_case(case: dict, extra: dict) -> tuple:
    """Case 12 (session_context): import-only branch -- see module
    docstring / spec: build_context_lines(root=<tmp outside the git
    tree>) is called directly, never via subprocess (the gate writes
    into the LIVE tree unconditionally when run as a subprocess,
    regardless of payload -- see tools/session_context.py itself)."""
    mod = _GATE_MODULES.get("session_context")
    if mod is None:
        return MISSING, "session_context module not importable"
    try:
        lines = mod.build_context_lines(root=Path(extra["tmp"]))
    except Exception as exc:
        if _looks_like_traceback(repr(exc)):
            return CRASH, repr(exc)
        return CRASH, f"{type(exc).__name__}: {exc}"
    if not lines:
        return DEAD, "build_context_lines() returned no lines at all"
    first = lines[0]
    if not (isinstance(first, str) and first.startswith("NOW: ")
            and first.endswith("(local system clock)")):
        return MISMATCH, f"unexpected first line: {first!r}"
    return OK, f"first line: {first!r}"


# --- composition sverka ---------------------------------------------------


def check_composition():
    """Returns (settings_unreadable: bool, case_missing: list, stale_case:
    list, info_lines: list) -- see module docstring, "VERDICTS"."""
    pairs = load_settings_hook_commands()
    if pairs is None:
        return True, [], [], []
    settings_scripts, info_lines = classify_settings_commands(pairs)
    case_scripts = {c["script"] for c in CASES}
    case_missing = sorted(settings_scripts - case_scripts)
    stale_case = sorted(case_scripts - settings_scripts)
    return False, case_missing, stale_case, info_lines


# --- top-level orchestration -----------------------------------------------


def run_all() -> dict:
    if not CASES:
        return {
            "no_cases": True,
            "settings_unreadable": False,
            "case_missing": [], "stale_case": [], "info_lines": [],
            "results": [], "live_state_diff": [], "import_findings": IMPORT_FINDINGS,
        }

    settings_unreadable, case_missing, stale_case, info_lines = check_composition()

    before = snapshot_live_state()
    results = [run_case(c) for c in CASES]
    after = snapshot_live_state()
    live_state_diff = diff_live_state(before, after)

    return {
        "no_cases": False,
        "settings_unreadable": settings_unreadable,
        "case_missing": case_missing,
        "stale_case": stale_case,
        "info_lines": info_lines,
        "results": results,
        "live_state_diff": live_state_diff,
        "import_findings": IMPORT_FINDINGS,
    }


def overall_ok(report: dict) -> bool:
    if report.get("no_cases"):
        return False
    if report["settings_unreadable"]:
        return False
    if report["case_missing"] or report["stale_case"]:
        return False
    if report["live_state_diff"]:
        return False
    return all(r["verdict"] == OK for r in report["results"])


def _cleanup_temp_dirs(report: dict) -> None:
    for r in report.get("results", []):
        tmp = r.get("tmp")
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)


def format_human_report(report: dict) -> str:
    lines = []
    if report.get("no_cases"):
        lines.append("NO-CASES: CASES table is empty -- probe defect, nothing ran.")
        return "\n".join(lines)

    if report["settings_unreadable"]:
        lines.append(f"SETTINGS-UNREADABLE: {SETTINGS_PATH}")

    for msg in report["case_missing"]:
        lines.append(f"CASE-MISSING: {msg} (hook registered, no matching probe case)")
    for msg in report["stale_case"]:
        lines.append(f"STALE-CASE: {msg} (probe case, no matching hook registration)")
    for msg in report["info_lines"]:
        lines.append(f"INFO: {msg}")
    for msg in report["import_findings"]:
        lines.append(f"FINDING: {msg}")

    for r in report["results"]:
        lines.append(f"[{r['verdict']}] {r['name']} ({r['script']}) -- {r['detail']}")

    for path in report["live_state_diff"]:
        lines.append(f"LIVE-STATE-TOUCHED: {path}")

    total = len(report["results"])
    ok_count = sum(1 for r in report["results"] if r["verdict"] == OK)
    dead_count = sum(1 for r in report["results"] if r["verdict"] == DEAD)
    silence_word = "\u043d\u043e\u043b\u044c \u043c\u043e\u043b\u0447\u0430\u043d\u0438\u0439" if dead_count == 0 else f"{dead_count} \u043c\u043e\u043b\u0447\u0430\u043d\u0438(\u0439)"
    lines.append(f"{ok_count}/{total} \u0436\u0438\u0432\u044b, {silence_word}")
    lines.append("SCOPE: code liveness only, not wiring liveness (see module docstring).")
    lines.append("OVERALL: " + (OK if overall_ok(report) else "NOT-OK"))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_all()
    try:
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            print(format_human_report(report))
    finally:
        _cleanup_temp_dirs(report)

    return 0 if overall_ok(report) else 1


if __name__ == "__main__":
    sys.exit(main())
