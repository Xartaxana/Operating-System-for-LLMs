"""WARN-layer firing-density meter -- kit port of the source deployment's
tools/warn_density.py. Measures FIRINGS, not MENTIONS: a source-side calibration
finding (class F10) found that counting layer NAMES living in source/
test/report/spec text overstated density by an order of magnitude. A
firing is recognized STRUCTURALLY: a transcript record carries
`attachment.type == "hook_success"`, its `attachment.stdout` (a JSON
string) is decoded with `json.loads`, and the registered literal (or an
alias, tools/warn_layers.json) is found inside
`hookSpecificOutput.additionalContext`. Parsing goes ONLY through
`json.loads`, never a raw-text grep -- the key "stdout" also shows up on
Bash tool results, and a layer's name can appear inside a message body
or a toolUseResult (exactly the class F10 exposed).

SOURCE: this deployment's session transcript JSONL files -- the
top-level `--transcripts` directory + `<session>/subagents/*.jsonl`.
The denominator is Z1 (tool_use calls matching the layer's OWN hook
matcher), not hook records: a silent PreToolUse hook leaves NO
attachment record at all between tool_use and tool_result, so the call
count cannot be read off hook records.

SIDECHAIN EXCLUSION: `hook_success`/`hook_additional_context` are
structurally never recorded for subagent (sidechain) tool_use -- a
sidechain hook fires (a live Bash call inside a subagent gets warned or
denied) but leaves no attachment trace anywhere in the transcript. That
is a property of the CARRIER (the sidechain stream is structurally
invisible), not a bug this tool can fix. Fix: Z1 and the "rate per 100
calls" only count MAIN-stream files (`is_sidechain_file()` -- a
`subagents/` directory); sidechain volume is printed every run as its
own line ("subagent stream invisible: N of M window calls"), never
silently dropped.

PER-LAYER REACHABLE POPULATION (ported from the source deployment's
node B, docs/tasks/2026-08-25_warn-population-class.md): the naive
denominator (every tool_use matching the layer's hook matcher) counts
calls the layer is STRUCTURALLY unable to fire on (e.g. a non-Bash tool
under a Bash-only barrier). The registry (`registry_version` 1 for this
kit copy) carries a declarative `reachable` field -- a CLOSED set of
kinds (`POPULATION_KINDS_MEASURED` below). Kit adaptation: only two
kinds are wired to a real predicate here --
`journal_path` (the six... well, four journal-echo layers this kit
tree actually carries: TIER_ECHO/WITNESS_ECHO/TS_DRIFT/ESCALATION --
barrier is `journal_echo._is_journal_path`, IMPORTED, not copied) and
`search_tool_or_pattern` (SEARCH_RETURNED_NOTHING --
`search_control_gate._looks_like_search` +
`_command_text_for_classification`, both IMPORTED). Every OTHER layer
in this kit's registry is honestly `"unmeasured"` with a `reason`:
either the barrier needs the gate's own parser (OWNS_OVERLAP,
BLIND_OWNS, NEGATIVE_CLAIM), or it is a property of the tool RESPONSE,
not the request (NEGATIVE_LINT), or it is a false-positive-class layer
whose denominator design is explicitly out of this node's scope
(GIVEN_PATH, ROLE_TYPE), or its population definition simply has not
been wired to a measured kind yet (HYGIENE). Barriers are imported from
their OWNING gate modules, never copied as a string literal -- the only
defence against the very recurrence class this design fixes (a gate
constant changes, the predicate here changes with it, no second edit).

Three numbers per layer: ACHIEVABLE (by declared `reachable`) /
UNREACHABLE (= matcher - achievable) / MATCHER (the old naive
denominator, kept alongside -- the "rate per 100 tool_use" stays on the
SAME single base, `total_tool_use_in_window`, for every layer, so it is
comparable ACROSS layers; the share, calls/achievable, is NOT --
each layer has its own achievable base). A layer with no declared
`reachable` (`"unmeasured"`) prints "n/a (population not declared:
<reason>)" and prints no percentage -- never a silent fallback to the
matcher number. `calls > achievable` is a PREDICATE DEFECT, exit 1.

Sidecar entries carry `population_rule_version` -- a machine-readable
way to tell windows measured before/after a predicate change apart
(`registry_sha` already changes automatically on any registry byte
edit, but an explicit version is insurance against an independent
predicate edit that happens not to touch the registry bytes).
`--no-sidecar` turns off BOTH reading and writing the sidecar, for
verification runs that should not grow `logs/warn_density.jsonl`.

CLI:
    python tools/warn_density.py [--window-start ISO] [--window-end ISO]
        [--registry-file PATH] [--transcripts DIR] [--sidecar PATH]
        [--json] [--no-sidecar]
    python tools/warn_density.py --check [--registry-file PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import os as _os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # console-safety on non-UTF8 Windows codepages
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# Barriers are IMPORTED from their owning gate modules, not copied --
# see the module docstring. Both modules live in tools/ next to this
# file -- either sys.path[0] Python sets running `python
# tools/warn_density.py` directly, or an explicit sys.path insert in
# tests (test_warn_density.py); both are already imported as modules by
# their own test_journal_echo.py/test_search_control_gate.py -- import
# safe (verified by reading: neither executes top-level code outside
# `if __name__ == "__main__":`).
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
import journal_echo as _journal_echo_gate  # noqa: E402
import search_control_gate as _search_control_gate  # noqa: E402

REPO_ROOT = _TOOLS_DIR.parent  # toolkit/
DEFAULT_REGISTRY = REPO_ROOT / "tools" / "warn_layers.json"
DEFAULT_SIDECAR = REPO_ROOT / "logs" / "warn_density.jsonl"
DEFAULT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"


def _default_transcripts_dir() -> Path:
    """Claude Code project directory slug -- every non-alnum character of
    the repo's absolute path is replaced with '-' (the observed
    convention; not re-derived here, just mirrored)."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO_ROOT.resolve()))
    return Path.home() / ".claude" / "projects" / slug


DEFAULT_TRANSCRIPTS = _default_transcripts_dir()

FIXTURE_EXPECTED_CALLS = 2
FIXTURE_EXPECTED_LINES = 3
_FIXTURE_LAYER_ID = "GIVEN_PATH"

# ---------------------------------------------------------------------------
# Per-layer reachable population (registry_version 1 for this kit copy).
# Order in POPULATION_KINDS_MEASURED is not significant (used as a
# membership set); "unmeasured" is separate and requires 'reason'
# (validate_layers).
# ---------------------------------------------------------------------------

POPULATION_KINDS_MEASURED = ("journal_path", "search_tool_or_pattern")
POPULATION_KINDS_ALL = POPULATION_KINDS_MEASURED + ("unmeasured",)

# Rule version for population COUNTING (not the registry's own
# registry_version) -- written into every new sidecar entry so windows
# before/after a predicate change are machine-distinguishable even if
# registry_sha happens not to change.
POPULATION_RULE_VERSION = 1

# Tool-name sets mirror the matcher group of the corresponding registry
# layers (tools/warn_layers.json) -- they bound the predicates below so
# reachability is never computed for a tool the barrier structurally
# does not touch.
_JOURNAL_LAYER_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"}
_SEARCH_LAYER_TOOL_NAMES = {"Bash", "PowerShell", "Grep", "Glob", "Read"}


def _population_journal_path(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Barrier of the journal-echo layers this kit carries (TIER_ECHO,
    WITNESS_ECHO, TS_DRIFT, ESCALATION) -- journal_echo only fires when
    `logs/routing-log.jsonl` is the edited path (journal_echo.py,
    `_is_journal_path`, imported not copied)."""
    if tool_name not in _JOURNAL_LAYER_TOOL_NAMES:
        return False
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return False
    return _journal_echo_gate._is_journal_path(file_path)


def _population_search_tool_or_pattern(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Barrier of SEARCH_RETURNED_NOTHING -- Grep/Glob always, Bash/
    PowerShell only for a search-shaped command (search_control_gate.py,
    `_looks_like_search` + `_command_text_for_classification`, both
    imported). Both functions are needed together: `_looks_like_search`
    alone does not gate `command_text` by tool_name -- a raw
    `tool_input` dict would falsely classify a non-Bash/PowerShell tool
    whose OTHER field happened to contain a search token."""
    if tool_name not in _SEARCH_LAYER_TOOL_NAMES:
        return False
    command_text = _search_control_gate._command_text_for_classification(tool_name, tool_input)
    return _search_control_gate._looks_like_search(tool_name, command_text)


POPULATION_PREDICATES = {
    "journal_path": _population_journal_path,
    "search_tool_or_pattern": _population_search_tool_or_pattern,
}


class SourceError(Exception):
    """--transcripts is not a directory / does not exist -- exit 2."""


class RegistryError(Exception):
    """Registry does not read STRUCTURALLY (not JSON / wrong top level)
    -- exit 2, nothing measurable at all."""


class ArgError(Exception):
    """Bad arguments (ISO, start>=end) -- exit 2, no traceback."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class LayerDef:
    id: str
    name: str
    carrier: List[str]
    symbol: Optional[str]
    literal: str
    aliases: List[str]
    hook_event: str
    matcher: str
    denominator: str
    listed_in_density_check: bool
    index: int = 0
    reachable: str = "unmeasured"
    reachable_reason: Optional[str] = None

    def all_strings(self) -> List[str]:
        return [self.literal] + list(self.aliases)


def read_registry_raw(path: Path) -> Tuple[int, List[Dict[str, Any]], bytes]:
    if not path.exists():
        raise RegistryError(f"registry not found: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RegistryError(f"registry is not UTF-8: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"registry is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError("registry: top level must be a JSON object")
    layers = data.get("layers")
    if not isinstance(layers, list):
        raise RegistryError("registry: 'layers' field missing or not a list")
    for i, item in enumerate(layers):
        if not isinstance(item, dict):
            raise RegistryError(f"registry: layers[{i}] is not a JSON object")
    return data.get("registry_version", 0), layers, raw


REQUIRED_LAYER_FIELDS = [
    "id", "name", "carrier", "literal", "aliases", "hook_event",
    "matcher", "denominator", "listed_in_density_check",
]


def validate_layers(raw_layers: List[Dict[str, Any]]) -> Tuple[List[LayerDef], List[str]]:
    """Returns (valid_layers, form_defects). One bad record does not
    abort the run (the "never a bare traceback" discipline) -- that
    record is excluded, the rest are still measured."""
    defects: List[str] = []
    valid: List[LayerDef] = []
    seen_ids: Dict[str, int] = {}
    for item in raw_layers:
        idv = item.get("id")
        if isinstance(idv, str):
            seen_ids[idv] = seen_ids.get(idv, 0) + 1
    dup_reported: set = set()

    for idx, item in enumerate(raw_layers):
        label = item.get("id") if isinstance(item.get("id"), str) else f"layers[{idx}]"
        ok = True
        for f in REQUIRED_LAYER_FIELDS:
            if f not in item:
                defects.append(f"FORM DEFECT: {label}: field '{f}' is missing")
                ok = False
        if not ok:
            continue
        idv = item["id"]
        if not isinstance(idv, str) or not idv:
            defects.append(f"FORM DEFECT: {label}: 'id' is not a non-empty string")
            ok = False
        elif seen_ids.get(idv, 0) > 1:
            if idv not in dup_reported:
                defects.append(f"FORM DEFECT: duplicate id: {idv} ({seen_ids[idv]} occurrences)")
                dup_reported.add(idv)
            ok = False
        carrier = item.get("carrier")
        if not isinstance(carrier, list) or not carrier:
            defects.append(f"FORM DEFECT: {label}: 'carrier' is empty or not a list")
            ok = False
        elif not all(isinstance(c, str) and c for c in carrier):
            defects.append(f"FORM DEFECT: {label}: 'carrier' carries a non-string/empty element")
            ok = False
        literal = item.get("literal")
        if not isinstance(literal, str) or not literal:
            defects.append(f"FORM DEFECT: {label}: 'literal' is empty or not a string")
            ok = False
        aliases = item.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            defects.append(f"FORM DEFECT: {label}: 'aliases' is not a list of strings")
            ok = False
            aliases = []
        # Adversarial battery: "{" in a literal/alias -- a whole format
        # template landed here instead of a static prefix.
        if isinstance(literal, str) and "{" in literal:
            defects.append(f"FORM DEFECT: {label}: '{{' in the literal -- a static prefix is required")
            ok = False
        if isinstance(aliases, list):
            for a in aliases:
                if isinstance(a, str) and "{" in a:
                    defects.append(f"FORM DEFECT: {label}: '{{' in an alias -- a static prefix is required")
                    ok = False
        # 'reachable' is OPTIONAL (a registry with no such field reads as
        # every layer unmeasured, exit 0, not a defect). A PRESENT but
        # syntactically bad value ("{"-template / empty string / number
        # / nested object / a kind outside the closed set) IS a form
        # defect -- the whole record is excluded (same discipline as
        # carrier/literal above).
        reachable = "unmeasured"
        reachable_reason: Optional[str] = "reachable is not declared in the registry"
        if "reachable" in item:
            reachable_raw = item.get("reachable")
            if not isinstance(reachable_raw, str) or not reachable_raw or "{" in reachable_raw:
                defects.append(f"FORM DEFECT: {label}: 'reachable' is syntactically bad")
                ok = False
            elif reachable_raw not in POPULATION_KINDS_ALL:
                defects.append(f"FORM DEFECT: {label}: 'reachable' is an unknown kind: {reachable_raw!r}")
                ok = False
            else:
                reachable = reachable_raw
                if reachable == "unmeasured":
                    reason_raw = item.get("reason")
                    if not isinstance(reason_raw, str) or not reason_raw.strip():
                        defects.append(
                            f"FORM DEFECT: {label}: reachable=unmeasured requires a non-empty 'reason'"
                        )
                        ok = False
                    else:
                        reachable_reason = reason_raw
                else:
                    reachable_reason = None
        if not ok:
            continue
        valid.append(LayerDef(
            id=idv, name=item.get("name", idv), carrier=carrier,
            symbol=item.get("symbol"), literal=literal, aliases=aliases,
            hook_event=item.get("hook_event", ""), matcher=item.get("matcher", ""),
            denominator=item.get("denominator", "Z1"),
            listed_in_density_check=bool(item.get("listed_in_density_check", False)),
            index=idx, reachable=reachable, reachable_reason=reachable_reason,
        ))

    # Literal overlap is FORBIDDEN by registry form: check every string
    # (literal + aliases) pairwise ACROSS DIFFERENT layers.
    all_strings: List[Tuple[str, str]] = []  # (layer_id, string)
    for l in valid:
        for s in l.all_strings():
            all_strings.append((l.id, s))
    for lid_a, sa in all_strings:
        for lid_b, sb in all_strings:
            if lid_a == lid_b:
                continue
            if sa == sb:
                continue
            if sa in sb:
                msg = f"FORM DEFECT: literal overlap: '{sa}' ({lid_a}) is a substring of '{sb}' ({lid_b})"
                if msg not in defects:
                    defects.append(msg)

    return valid, defects


# A carrier may assemble a message from adjacent Python string literals
# ("...text one "\n    "text two...") that the runtime concatenates into
# ONE string, while the raw SOURCE text carries a newline/indent between
# them. A naive substring search over raw carrier text then falsely
# misses a LIVE, correctly-working literal. Liveness is checked against
# text with concatenation SEAMS flattened: a closing quote, only
# whitespace/newline, an opening quote of the SAME kind -- the seam is
# removed, content stays identical (nothing invented).
_CONCAT_SEAM_RE = re.compile(r'"\s*\n\s*"|\'\s*\n\s*\'')


def _flatten_concat_seams(text: str) -> str:
    return _CONCAT_SEAM_RE.sub("", text)


def check_liveness(layer: LayerDef, root: Path) -> Tuple[bool, str]:
    """(i) literal liveness: the literal MUST be found in the carrier
    file (by reading, not by memory). Any carrier in the list carrying
    the literal or an alias is enough (carrier is a list)."""
    for rel in layer.carrier:
        full = root / rel
        if not full.exists():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        flattened = _flatten_concat_seams(text)
        for s in layer.all_strings():
            if s in text or s in flattened:
                return True, f"alive in {rel}"
    return False, "not found in any carrier"


def check_symbol_binding(layer: LayerDef, root: Path) -> Optional[str]:
    """(ii) binding to a named constant -- ONLY when symbol is not null
    (not every layer has one). Returns None (ok / not applicable) or a
    defect string."""
    if layer.symbol is None:
        return None
    for rel in layer.carrier:
        full = root / rel
        if not full.exists():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf"\b{re.escape(layer.symbol)}\b\s*(:.*)?=", text):
            return None
    return f"REGISTRY DEFECT: {layer.id}: symbol '{layer.symbol}' not found as an assignment in any carrier"


# ---------------------------------------------------------------------------
# Reconciliation against the calibration protocol's density check
# ---------------------------------------------------------------------------

def parse_density_check_names(protocol_text: str) -> Optional[List[str]]:
    """Extracts layer names from the WARN LAYER DENSITY block of
    PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md. Returns None if the block is
    not found (protocol form drifted -- printed as a finding, not a
    crash)."""
    idx = protocol_text.find("WARN LAYER DENSITY")
    if idx == -1:
        return None
    end_idx = protocol_text.find("LIST IS OPEN", idx)
    if end_idx == -1:
        end_idx = idx + 2000
    block = protocol_text[idx:end_idx]
    marker = "Layers and carriers:"
    m_idx = block.find(marker)
    if m_idx == -1:
        return None
    block = block[m_idx + len(marker):]
    normalized = re.sub(r"\s+", " ", block).strip()
    names: List[str] = []
    for segment in normalized.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        seg = re.split(r"\s+--\s+tools/", segment)[0]
        seg = re.sub(r"\([^)]*\)", "", seg)
        for name in seg.split(","):
            name = name.strip().strip(".")
            if name:
                names.append(name)
    return names


def diff_density_check(layers: List[LayerDef], check_names: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    """Returns (in_check_not_registry, in_registry_not_check)."""
    if check_names is None:
        return [], []
    check_set = set(check_names)
    registry_all = {l.name for l in layers}
    in_check_not_registry = sorted(check_set - registry_all)
    in_registry_not_check = sorted(registry_all - check_set)
    return in_check_not_registry, in_registry_not_check


# ---------------------------------------------------------------------------
# Hook settings -- proxy detection (several scripts sharing one matcher)
# ---------------------------------------------------------------------------

def load_hook_multiplicity(settings_path: Path) -> Dict[Tuple[str, str], int]:
    """(hook_event, matcher) -> number of registered command hooks. >1
    means this matcher's Z1 is shared between several carriers (proxy)."""
    result: Dict[Tuple[str, str], int] = {}
    if not settings_path.exists():
        return result
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return result
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "")
            cmds = group.get("hooks", [])
            n = len(cmds) if isinstance(cmds, list) else 0
            key = (event, matcher)
            result[key] = result.get(key, 0) + n
    return result


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

ISO_LOCAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def parse_window_bound(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    if not ISO_LOCAL_RE.match(s):
        raise ArgError(f"not an ISO local naive time (YYYY-MM-DDTHH:MM:SS): {s!r}")
    try:
        naive = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ArgError(f"invalid date/time: {s!r} ({exc})") from exc
    # A naive datetime is interpreted by astimezone() as the system's
    # LOCAL time.
    return naive.astimezone()


def parse_transcript_ts(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Corpus: file enumeration (top level + subagents/)
# ---------------------------------------------------------------------------

def enumerate_corpus_files(transcripts_dir: Path) -> List[Path]:
    if not transcripts_dir.exists() or not transcripts_dir.is_dir():
        raise SourceError(f"--transcripts is not a directory / does not exist: {transcripts_dir}")
    files: List[Path] = sorted(transcripts_dir.glob("*.jsonl"))
    for sub in sorted(transcripts_dir.iterdir()):
        if not sub.is_dir():
            continue
        agents_dir = sub / "subagents"
        if agents_dir.is_dir():
            files.extend(sorted(agents_dir.glob("*.jsonl")))
    return files


def is_sidechain_file(path: Path) -> bool:
    """A subagent (sidechain) file lives under `<session>/subagents/`.
    hook_success/hook_additional_context are NEVER recorded on subagent
    calls (a property of the carrier, not a bug), so tool_use from these
    files cannot physically supply a numerator -- an honest denominator
    counts main-stream files only."""
    return path.parent.name == "subagents"


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

@dataclass
class LayerCounts:
    calls: int = 0
    lines: int = 0
    raw_calls: int = 0
    raw_lines: int = 0


@dataclass
class Report:
    layers: List[LayerDef]
    counts: Dict[str, LayerCounts]
    tool_use_counts: Dict[str, int]
    total_tool_use_in_window: int
    dedup_dropped: int
    total_hook_success: int
    total_hook_additional_context: int
    silent_hook_success: int
    raw_parse_failed: int
    no_timestamp: int
    fallback_key_count: int
    transcripts_dir: Path
    total_lines_seen: int
    broken_lines: int
    files_read: int
    total_bytes: int
    in_window_records: int
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    proxy_map: Dict[Tuple[str, str], int]
    fixture_calls: int
    fixture_lines: int
    sidechain_tool_use_in_window: int
    orphan_hac_count: int
    duplicate_tool_use_id_count: int
    population_achievable_counts: Dict[str, int]


def process_corpus(
    files: List[Path], layers: List[LayerDef],
    window_start: Optional[datetime], window_end: Optional[datetime],
    proxy_map: Dict[Tuple[str, str], int],
    transcripts_dir: Optional[Path] = None,
    compute_fixture: bool = True,
) -> Report:
    seen: set = set()
    seen_raw: set = set()
    counts: Dict[str, LayerCounts] = {l.id: LayerCounts() for l in layers}
    tool_use_counts: Dict[str, int] = {}
    total_tool_use_in_window = 0
    sidechain_tool_use_in_window = 0
    dedup_dropped = 0
    total_hook_success = 0
    total_hook_additional_context = 0
    silent_hook_success = 0
    raw_parse_failed = 0
    no_timestamp = 0
    fallback_key_count = 0
    total_lines_seen = 0
    broken_lines = 0
    total_bytes = 0
    in_window_records = 0
    duplicate_tool_use_id_count = 0
    # Sum of ACHIEVABLE population by each `reachable` KIND (not by
    # layer -- several layers can share one kind, e.g. all four journal
    # layers read the "journal_path" key).
    population_achievable_counts: Dict[str, int] = {k: 0 for k in POPULATION_KINDS_MEASURED}
    tool_use_ids_seen: set = set()
    orphan_hac_count = 0

    # hook_additional_context WITHOUT a paired hook_success by key
    # (unit_key, hookName) is the ONLY trace of a firing. The pair may
    # physically live LATER in the same file or in another corpus file,
    # so hac is buffered and reconciled against success_keys AFTER the
    # full pass over every file (order-independent).
    success_keys: set = set()
    hac_buffer: List[Tuple[str, str, List[str]]] = []  # (unit_key, hook_name, content)

    for f in files:
        is_side = is_sidechain_file(f)
        try:
            total_bytes += f.stat().st_size
        except OSError:
            pass
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            continue
        with fh:
            for line_no, raw_ln in enumerate(fh, start=1):
                ln = raw_ln.strip()
                if not ln:
                    continue
                total_lines_seen += 1
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    broken_lines += 1
                    continue
                if not isinstance(rec, dict):
                    broken_lines += 1
                    continue

                dt = parse_transcript_ts(rec.get("timestamp"))
                if dt is None:
                    no_timestamp += 1
                    continue
                if window_start is not None and dt < window_start:
                    continue
                if window_end is not None and dt >= window_end:
                    continue
                in_window_records += 1

                if rec.get("type") == "assistant":
                    msg = rec.get("message")
                    if isinstance(msg, dict):
                        content = msg.get("content")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                    name = item.get("name")
                                    if isinstance(name, str):
                                        if is_side:
                                            sidechain_tool_use_in_window += 1
                                        else:
                                            item_id = item.get("id")
                                            if isinstance(item_id, str) and item_id:
                                                if item_id in tool_use_ids_seen:
                                                    duplicate_tool_use_id_count += 1
                                                else:
                                                    tool_use_ids_seen.add(item_id)
                                            tool_input = item.get("input")
                                            if not isinstance(tool_input, dict):
                                                tool_input = {}
                                            for kind, pred in POPULATION_PREDICATES.items():
                                                if pred(name, tool_input):
                                                    population_achievable_counts[kind] += 1
                                            tool_use_counts[name] = tool_use_counts.get(name, 0) + 1
                                            total_tool_use_in_window += 1

                att = rec.get("attachment")
                if not isinstance(att, dict):
                    continue
                atype = att.get("type")
                if atype not in ("hook_success", "hook_additional_context"):
                    continue

                tool_use_id = att.get("toolUseID")
                hook_name = att.get("hookName") or ""
                if isinstance(tool_use_id, str) and tool_use_id:
                    unit_key = tool_use_id
                else:
                    uuid_ = rec.get("uuid")
                    if isinstance(uuid_, str) and uuid_:
                        unit_key = f"uuid:{uuid_}"
                    else:
                        unit_key = f"fallback:{f}:{line_no}"
                        fallback_key_count += 1

                if atype == "hook_additional_context":
                    total_hook_additional_context += 1
                    content = att.get("content")
                    if isinstance(content, list):
                        texts = [c for c in content if isinstance(c, str)]
                    elif isinstance(content, str):
                        texts = [content]
                    else:
                        texts = []
                    hac_buffer.append((unit_key, hook_name, texts))
                    continue
                total_hook_success += 1
                success_keys.add((unit_key, hook_name))

                stdout = att.get("stdout")
                if not isinstance(stdout, str) or stdout.strip() == "":
                    silent_hook_success += 1
                    continue

                ctx: Optional[str] = None
                parse_ok = True
                try:
                    obj = json.loads(stdout)
                except (json.JSONDecodeError, TypeError, ValueError):
                    parse_ok = False
                    obj = None

                if parse_ok:
                    if isinstance(obj, dict):
                        hso = obj.get("hookSpecificOutput")
                        if isinstance(hso, dict):
                            v = hso.get("additionalContext")
                            if isinstance(v, str):
                                ctx = v
                    if ctx is None:
                        continue
                    for layer in layers:
                        hits = sum(ctx.count(s) for s in layer.all_strings())
                        if hits <= 0:
                            continue
                        dkey = (unit_key, hook_name, layer.id)
                        if dkey in seen:
                            dedup_dropped += 1
                            continue
                        seen.add(dkey)
                        c = counts[layer.id]
                        c.calls += 1
                        c.lines += hits
                else:
                    # Total stdout parse failure -- fall back to a plain
                    # substring search over the raw text (kept simple:
                    # every registered literal in this kit's registry is
                    # pure ASCII, so no dual-form JSON-escape search is
                    # needed here -- an adaptation from the source
                    # deployment's raw-fallback, named in the port
                    # report).
                    raw_parse_failed += 1
                    for layer in layers:
                        hits = sum(stdout.count(s) for s in layer.all_strings())
                        if hits <= 0:
                            continue
                        dkey = (unit_key, hook_name, layer.id)
                        if dkey in seen_raw:
                            continue
                        seen_raw.add(dkey)
                        c = counts[layer.id]
                        c.raw_calls += 1
                        c.raw_lines += hits

    # Second pass (in memory, not per-file): hac with no paired
    # hook_success by (unit_key, hook_name) -- the ONLY trace of that
    # firing, must be counted. Reuses the SAME `seen` dedup set so a
    # repeated orphan record of the same key isn't double-counted.
    for unit_key, hook_name, texts in hac_buffer:
        if (unit_key, hook_name) in success_keys:
            continue  # a pair exists -- not orphaned, ignored entirely
        orphan_hac_count += 1
        if not texts:
            continue
        for layer in layers:
            hits = sum(sum(t.count(s) for t in texts) for s in layer.all_strings())
            if hits <= 0:
                continue
            dkey = (unit_key, hook_name, layer.id)
            if dkey in seen:
                dedup_dropped += 1
                continue
            seen.add(dkey)
            c = counts[layer.id]
            c.calls += 1
            c.lines += hits

    if compute_fixture:
        fixture_calls, fixture_lines = fixture_control(layers)
    else:
        fixture_calls, fixture_lines = 0, 0

    return Report(
        layers=layers, counts=counts, tool_use_counts=tool_use_counts,
        total_tool_use_in_window=total_tool_use_in_window,
        dedup_dropped=dedup_dropped, total_hook_success=total_hook_success,
        total_hook_additional_context=total_hook_additional_context,
        silent_hook_success=silent_hook_success,
        raw_parse_failed=raw_parse_failed, no_timestamp=no_timestamp,
        fallback_key_count=fallback_key_count,
        transcripts_dir=transcripts_dir if transcripts_dir is not None else Path("."),
        total_lines_seen=total_lines_seen, broken_lines=broken_lines,
        files_read=len(files), total_bytes=total_bytes,
        in_window_records=in_window_records,
        window_start=window_start, window_end=window_end,
        proxy_map=proxy_map, fixture_calls=fixture_calls, fixture_lines=fixture_lines,
        sidechain_tool_use_in_window=sidechain_tool_use_in_window,
        orphan_hac_count=orphan_hac_count,
        duplicate_tool_use_id_count=duplicate_tool_use_id_count,
        population_achievable_counts=population_achievable_counts,
    )


# ---------------------------------------------------------------------------
# Built-in fixture: a positive hit + a deliberately non-structural
# occurrence of the layer name in a message body / toolUseResult -- a RED
# control.
# ---------------------------------------------------------------------------

def _fixture_records() -> List[str]:
    """Synthetic mini-transcript JSONL lines. Expectation: calls=2 (two
    distinct units carry GIVEN-PATH WARN), lines=3 (1+2 occurrences).
    Record 3 (assistant text) and record 4 (toolUseResult) carry the
    LAYER NAME in a NON-structural place -- they must add NOTHING (the
    red control)."""
    rec1 = {
        "uuid": "fixture-uuid-1",
        "timestamp": "2026-01-01T00:00:01.000Z",
        "attachment": {
            "type": "hook_success",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-1",
            "stdout": json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "GIVEN-PATH WARN: paths do not exist: a",
                }
            }, ensure_ascii=False),
        },
    }
    rec2 = {
        "uuid": "fixture-uuid-2",
        "timestamp": "2026-01-01T00:00:02.000Z",
        "attachment": {
            "type": "hook_success",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-2",
            "stdout": json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": (
                        "GIVEN-PATH WARN: paths do not exist: a; "
                        "GIVEN-PATH WARN: paths do not exist: b"
                    ),
                }
            }, ensure_ascii=False),
        },
    }
    # NOT hook_success -- the layer name is in the ASSISTANT'S message
    # body (red control): must not be counted.
    rec3 = {
        "uuid": "fixture-uuid-3",
        "timestamp": "2026-01-01T00:00:03.000Z",
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "see GIVEN-PATH WARN: above"}]},
    }
    # NOT hook_success -- the layer name is in a toolUseResult (a tool's
    # own output, e.g. a manual grep) -- red control.
    rec4 = {
        "uuid": "fixture-uuid-4",
        "timestamp": "2026-01-01T00:00:04.000Z",
        "type": "user",
        "message": {"content": [{
            "type": "tool_result",
            "content": "grep output: GIVEN-PATH WARN: paths do not exist: z",
        }]},
    }
    # A second trace of the SAME firing -- ignored entirely (already has
    # a hook_success pair).
    rec5 = {
        "uuid": "fixture-uuid-5",
        "timestamp": "2026-01-01T00:00:05.000Z",
        "attachment": {
            "type": "hook_additional_context",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-1",
        },
    }
    return [json.dumps(r, ensure_ascii=False) for r in (rec1, rec2, rec3, rec4, rec5)]


def fixture_control(layers: List[LayerDef]) -> Tuple[int, int]:
    """Runs the built-in fixture through the SAME process_corpus that
    real data uses -- no separate counting logic (otherwise the fixture
    would prove nothing about the real counter)."""
    fixture_layers = [l for l in layers if l.id == _FIXTURE_LAYER_ID]
    if not fixture_layers:
        # A registry with no fixture layer cannot compute the fixture
        # (0/0 is printed as an explicit defect by the caller).
        return 0, 0
    fd, path = tempfile.mkstemp(suffix=".jsonl", prefix="warn_density_fixture_")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as fh:
            for ln in _fixture_records():
                fh.write(ln + "\n")
        rep = process_corpus(
            [Path(path)], fixture_layers, window_start=None, window_end=None,
            proxy_map={}, compute_fixture=False,
        )
        c = rep.counts[_FIXTURE_LAYER_ID]
        return c.calls, c.lines
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Sidecar
# ---------------------------------------------------------------------------

def registry_sha(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def read_sidecar_last(path: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    if not path.exists():
        return None, []
    warnings: List[str] = []
    last: Optional[Dict[str, Any]] = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, ln in enumerate(fh, start=1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                last = json.loads(ln)
            except json.JSONDecodeError as exc:
                warnings.append(f"broken sidecar line {path}:{line_no}: {exc}")
    return last, warnings


def write_sidecar_entry(path: Path, entry: Dict[str, Any]) -> Optional[str]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return None
    except OSError as exc:
        return f"sidecar not written ({path}): {exc}"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_dt_both(dt: Optional[datetime]) -> str:
    if dt is None:
        return "(no boundary)"
    local_naive = dt.astimezone().replace(tzinfo=None).isoformat()
    utc = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"local {local_naive} / UTC {utc}"


def layer_matcher_total(layer: LayerDef, tool_use_counts: Dict[str, int]) -> int:
    """The naive denominator -- sum of tool_use for ANY tool named in the
    layer's matcher, with no reachability filter. Printed alongside
    achievable/unreachable as a separate number, NOT used as the share's
    denominator (see layer_population below); the "rate per 100 calls"
    also does not use this number -- it uses total_tool_use_in_window,
    the single shared base."""
    names = [n for n in layer.matcher.split("|") if n]
    return sum(tool_use_counts.get(n, 0) for n in names)


def layer_population(layer: LayerDef, report: "Report") -> Tuple[Optional[int], Optional[int], int]:
    """Returns (achievable, unreachable, matcher). achievable/unreachable
    are None when layer.reachable == "unmeasured" (prints "n/a
    (population not declared: <reason>)", never a silent fallback to the
    matcher). When reachable is a measured kind: achievable = the sum of
    population_achievable_counts for that kind over the window (the same
    raw, non-deduplicated basis as the matcher total); unreachable =
    matcher - achievable (clipped to 0 defensively)."""
    matcher_total = layer_matcher_total(layer, report.tool_use_counts)
    if layer.reachable not in POPULATION_KINDS_MEASURED:
        return None, None, matcher_total
    achievable = report.population_achievable_counts.get(layer.reachable, 0)
    unreachable = max(matcher_total - achievable, 0)
    return achievable, unreachable, matcher_total


def layer_is_proxy(layer: LayerDef, proxy_map: Dict[Tuple[str, str], int]) -> bool:
    """proxy=true -- several hook scripts are registered on the SAME
    (hook_event, matcher) in .claude/settings.json -- this layer's
    MATCHER traffic is shared with another carrier, not exclusive to
    this one. This is a statement about the MATCHER
    (layer_matcher_total), not about the ACHIEVABLE population
    (layer_population) -- the per-layer denominator does not change this
    logic; proxy stays a property of hook registration in settings.json."""
    return proxy_map.get((layer.hook_event, layer.matcher), 0) > 1


def compute_run_defects(report: Report) -> List[str]:
    """Defects printed by BOTH renderers (text/json) and deciding a
    normal run's exit code -- never a bare zero with no verdict.
    `calls > achievable` is the population predicate having caught up
    with reality, caught by its own measurement."""
    defects: List[str] = []
    if report.total_lines_seen > 0 and report.broken_lines == report.total_lines_seen:
        defects.append(f"SOURCE DEFECT: 100% of lines are broken ({report.broken_lines}/{report.total_lines_seen})")
    if report.fixture_calls != FIXTURE_EXPECTED_CALLS or report.fixture_lines != FIXTURE_EXPECTED_LINES:
        defects.append(
            f"TOOL DEFECT: fixture {report.fixture_calls}/{FIXTURE_EXPECTED_CALLS} calls, "
            f"{report.fixture_lines}/{FIXTURE_EXPECTED_LINES} lines do not match"
        )
    for layer in report.layers:
        achievable, _unreachable, _matcher = layer_population(layer, report)
        if achievable is None:
            continue
        c = report.counts.get(layer.id)
        if c is None:
            continue
        if c.calls > achievable:
            defects.append(
                f"PREDICATE DEFECT: {layer.id}: calls={c.calls} > achievable={achievable}"
            )
    return defects


def render_text(
    report: Report, root: Path, check_names: Optional[List[str]],
    base_status: str, sidecar_warn: Optional[str], source_empty: bool,
) -> str:
    out: List[str] = []
    out.append("=== SOURCE CONTROL ===")
    out.append(f"  directory: {report.transcripts_dir}")
    out.append(f"  files: {report.files_read} | bytes: {report.total_bytes}")
    out.append(f"  window: start={_fmt_dt_both(report.window_start)} end={_fmt_dt_both(report.window_end)}")
    out.append(f"  fixture (built-in positive+red control): "
               f"{report.fixture_calls}/{FIXTURE_EXPECTED_CALLS} calls, "
               f"{report.fixture_lines}/{FIXTURE_EXPECTED_LINES} lines")
    out.append(f"  baseline: {base_status}")
    if sidecar_warn:
        out.append(f"  WARN: {sidecar_warn}")
    if source_empty:
        out.append("  SOURCE EMPTY: directory exists, 0 files")
    out.append(f"  dedup: {report.dedup_dropped} duplicate records dropped")
    out.append(f"  second traces (hook_additional_context): {report.total_hook_additional_context} "
               f"(hook_success: {report.total_hook_success}, "
               f"orphaned with no hook_success pair: {report.orphan_hac_count})")
    _sidechain_total = report.total_tool_use_in_window + report.sidechain_tool_use_in_window
    out.append(
        f"  subagent stream invisible: {report.sidechain_tool_use_in_window} "
        f"of {_sidechain_total} window calls (the denominator counts main-stream only)"
    )
    out.append(
        f"  dedup is asymmetric: the numerator is deduplicated, the tool_use denominator is not; "
        f"duplicate ids in window: {report.duplicate_tool_use_id_count} of "
        f"{report.total_tool_use_in_window} (not subtracted -- effect is negligible now, "
        f"grows on a re-written transcript)"
    )
    out.append(f"  no timestamp: {report.no_timestamp}")
    out.append(f"  fallback key (no toolUseID and no uuid): {report.fallback_key_count}")
    out.append(f"  silent hook_success (empty stdout): {report.silent_hook_success}")
    out.append(f"  stdout does not parse as JSON (raw fallback): {report.raw_parse_failed}")
    if report.total_lines_seen > 0:
        pct_broken = report.broken_lines / report.total_lines_seen * 100
        out.append(f"  broken JSONL lines: {report.broken_lines}/{report.total_lines_seen} ({pct_broken:.1f}%)")
    else:
        out.append("  broken JSONL lines: 0/0")
    if report.in_window_records == 0:
        out.append("WINDOW EMPTY: 0 records")

    out.append("\n=== LAYERS ===")
    out.append(
        "  (share: calls / ACHIEVABLE -- the base is DIFFERENT per layer, not comparable across layers)"
    )
    out.append(
        "  (rate: calls / total_tool_use_in_window*100 -- ONE shared base for every layer, "
        "comparable ACROSS layers)"
    )
    not_fired: List[str] = []
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        proxy = layer_is_proxy(layer, report.proxy_map)
        if achievable is None:
            pop_str = f"achievable=n/a unreachable=n/a matcher={matcher_total}"
            share_str = f"n/a (population not declared: {layer.reachable_reason})"
        else:
            pop_str = f"achievable={achievable} unreachable={unreachable} matcher={matcher_total}"
            if achievable == 0:
                share_str = f"n/a (achievable 0 of {matcher_total})"
            else:
                share_str = f"{c.calls / achievable * 100:.1f}%"
        if report.total_tool_use_in_window == 0:
            rate_str = "n/a (denominator 0)"
        else:
            rate_str = f"{c.calls / report.total_tool_use_in_window * 100:.2f}/100"
        proxy_tag = " matcher-proxy" if proxy else ""
        out.append(
            f"  {layer.id} [{layer.name}]: calls={c.calls} lines={c.lines} "
            f"(+raw calls={c.raw_calls} lines={c.raw_lines}) "
            f"{pop_str}{proxy_tag} share={share_str} rate={rate_str} "
            f"in_density_check={'yes' if layer.listed_in_density_check else 'no'}"
        )
        if c.calls == 0 and report.in_window_records > 0:
            not_fired.append(layer.id)

    out.append("\n=== DID NOT FIRE ===")
    if not_fired:
        for lid in not_fired:
            layer = next(l for l in report.layers if l.id == lid)
            alive, reason = check_liveness(layer, root)
            verdict = f"alive ({reason})" if alive else "REGISTRY DEFECT (literal not found in carrier)"
            out.append(f"  {lid} [{layer.name}]: {verdict}")
    else:
        out.append("  (none)" if report.in_window_records > 0 else "  (window empty -- no verdict rendered)")

    out.append("\n=== DEFECTS ===")
    defects: List[str] = compute_run_defects(report)
    if defects:
        for d in defects:
            out.append(f"  {d}")
    else:
        out.append("  (no defects)")

    out.append("\n=== FINDINGS ABOUT THE CHECK ===")
    in_check_not_reg, in_reg_not_check = diff_density_check(report.layers, check_names)
    if check_names is None:
        out.append("  (the WARN LAYER DENSITY block was not recognized in the protocol -- reconciliation skipped)")
    else:
        if in_check_not_reg:
            out.append(f"  named in the check, missing from the registry: {', '.join(in_check_not_reg)}")
        if in_reg_not_check:
            out.append(f"  in the registry, not named in the check (FINDING, the check's list is open): "
                       f"{', '.join(in_reg_not_check)}")
        if not in_check_not_reg and not in_reg_not_check:
            out.append("  (reconciled)")

    total_calls = sum(c.calls for c in report.counts.values())
    out.append(f"\nSUMMARY: layers {len(report.layers)} - calls total {total_calls} - "
               f"tool_use in window {report.total_tool_use_in_window}")
    return "\n".join(out)


def build_sidecar_entry(report: Report, registry_hash: str) -> Dict[str, Any]:
    layers_map = {}
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        layers_map[layer.id] = {
            "calls": c.calls, "lines": c.lines,
            "raw_calls": c.raw_calls, "raw_lines": c.raw_lines,
            "denominator": matcher_total,
            "reachable": layer.reachable,
            "achievable": achievable,
            "unreachable": unreachable,
            "matcher": matcher_total,
        }
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "registry_sha": registry_hash,
        "population_rule_version": POPULATION_RULE_VERSION,
        "window_start": report.window_start.isoformat() if report.window_start else None,
        "window_end": report.window_end.isoformat() if report.window_end else None,
        "layers": layers_map,
        "total_tool_use_in_window": report.total_tool_use_in_window,
    }


def render_json(report: Report, root: Path, check_names: Optional[List[str]]) -> str:
    layers_out = []
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        layers_out.append({
            "id": layer.id, "name": layer.name, "calls": c.calls, "lines": c.lines,
            "raw_calls": c.raw_calls, "raw_lines": c.raw_lines,
            "denominator": matcher_total, "proxy": layer_is_proxy(layer, report.proxy_map),
            "reachable": layer.reachable, "reachable_reason": layer.reachable_reason,
            "achievable": achievable, "unreachable": unreachable, "matcher": matcher_total,
            "listed_in_density_check": layer.listed_in_density_check,
        })
    in_check_not_reg, in_reg_not_check = diff_density_check(report.layers, check_names)
    payload = {
        "files_read": report.files_read, "total_bytes": report.total_bytes,
        "fixture_calls": report.fixture_calls, "fixture_lines": report.fixture_lines,
        "dedup_dropped": report.dedup_dropped,
        "no_timestamp": report.no_timestamp, "silent_hook_success": report.silent_hook_success,
        "raw_parse_failed": report.raw_parse_failed,
        "broken_lines": report.broken_lines, "total_lines_seen": report.total_lines_seen,
        "in_window_records": report.in_window_records,
        "total_tool_use_in_window": report.total_tool_use_in_window,
        "sidechain_tool_use_in_window": report.sidechain_tool_use_in_window,
        "orphan_hac_count": report.orphan_hac_count,
        "duplicate_tool_use_id_count": report.duplicate_tool_use_id_count,
        "layers": layers_out,
        "density_check_diff": {"in_check_not_registry": in_check_not_reg, "in_registry_not_check": in_reg_not_check},
        "defects": compute_run_defects(report),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------

def scan_corpus_health(files: List[Path]) -> Tuple[int, int]:
    """(total_lines_seen, broken_lines) -- a light scan with NO layer
    parsing, only structural JSONL integrity."""
    total = 0
    broken = 0
    for f in files:
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            continue
        with fh:
            for ln in fh:
                s = ln.strip()
                if not s:
                    continue
                total += 1
                try:
                    json.loads(s)
                except json.JSONDecodeError:
                    broken += 1
    return total, broken


def run_check(registry_path: Path, root: Path, transcripts_dir: Optional[Path] = None) -> Tuple[str, int]:
    out: List[str] = []
    try:
        _, raw_layers, _raw_bytes = read_registry_raw(registry_path)
    except RegistryError as exc:
        return f"warn_density --check: {exc}", 2
    layers, form_defects = validate_layers(raw_layers)
    defects = list(form_defects)
    for layer in layers:
        alive, reason = check_liveness(layer, root)
        if not alive:
            defects.append(f"REGISTRY DEFECT: {layer.id}: {reason}")
        sym_defect = check_symbol_binding(layer, root)
        if sym_defect:
            defects.append(sym_defect)
    out.append("=== --check: REGISTRY ===")
    out.append(f"  layers in registry: {len(raw_layers)} (valid: {len(layers)})")
    if defects:
        for d in defects:
            out.append(f"  {d}")
    else:
        out.append("  (no defects)")

    # --check additionally reacts to source FORM when it resolves, but
    # does not REQUIRE it to exist -- a hard requirement on transcripts
    # would make --check brittle in an environment where
    # .claude/projects/<slug> does not exist.
    if transcripts_dir is not None and transcripts_dir.exists() and transcripts_dir.is_dir():
        try:
            files = enumerate_corpus_files(transcripts_dir)
        except SourceError:
            files = []
        out.append("=== --check: SOURCE ===")
        if not files:
            out.append(f"  SOURCE EMPTY: {transcripts_dir} exists, 0 files")
            defects.append(f"SOURCE EMPTY: {transcripts_dir}")
        else:
            total, broken = scan_corpus_health(files)
            out.append(f"  files: {len(files)} | lines: {total} | broken: {broken}")
            if total > 0 and broken == total:
                msg = f"SOURCE DEFECT: 100% of lines are broken ({broken}/{total})"
                out.append(f"  {msg}")
                defects.append(msg)

    return "\n".join(out), (1 if defects else 0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--window-start", default=None)
    p.add_argument("--window-end", default=None)
    p.add_argument("--registry-file", default=str(DEFAULT_REGISTRY))
    p.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
    p.add_argument("--sidecar", default=str(DEFAULT_SIDECAR))
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument(
        "--no-sidecar", action="store_true",
        help="Do not read or write logs/warn_density.jsonl -- for "
             "verification runs that should not grow the sidecar.",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    registry_path = Path(args.registry_file)
    root = REPO_ROOT

    if args.check:
        transcripts_dir = Path(args.transcripts) if args.transcripts else None
        text, code = run_check(registry_path, root, transcripts_dir)
        print(text)
        return code

    try:
        window_start = parse_window_bound(args.window_start)
        window_end = parse_window_bound(args.window_end)
    except ArgError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    if window_start is not None and window_end is not None and window_start >= window_end:
        print("warn_density: --window-start >= --window-end", file=sys.stderr)
        return 2

    try:
        _, raw_layers, raw_bytes = read_registry_raw(registry_path)
    except RegistryError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    layers, _form_defects = validate_layers(raw_layers)

    transcripts_dir = Path(args.transcripts)
    try:
        files = enumerate_corpus_files(transcripts_dir)
    except SourceError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    source_empty = len(files) == 0

    proxy_map = load_hook_multiplicity(Path(args.settings))
    report = process_corpus(files, layers, window_start, window_end, proxy_map, transcripts_dir)

    protocol_path = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
    check_names: Optional[List[str]] = None
    if protocol_path.exists():
        try:
            check_names = parse_density_check_names(protocol_path.read_text(encoding="utf-8"))
        except OSError:
            check_names = None

    reg_hash = registry_sha(raw_bytes)
    if args.no_sidecar:
        base_status = "RECONCILIATION SKIPPED (--no-sidecar)"
        sidecar_warn: Optional[str] = None
    else:
        sidecar_path = Path(args.sidecar)
        last_entry, sidecar_read_warnings = read_sidecar_last(sidecar_path)
        if last_entry is None:
            base_status = "NO BASELINE"
        elif last_entry.get("registry_sha") != reg_hash:
            base_status = "BASELINE FROM A DIFFERENT REGISTRY"
        elif last_entry.get("population_rule_version") != POPULATION_RULE_VERSION:
            base_status = "BASELINE PREDATES THE PER-LAYER DENOMINATOR (population_rule_version missing/stale)"
        else:
            base_status = "OK"

        sidecar_entry = build_sidecar_entry(report, reg_hash)
        sidecar_warn = write_sidecar_entry(sidecar_path, sidecar_entry)
        for w in sidecar_read_warnings:
            sidecar_warn = (sidecar_warn + "; " + w) if sidecar_warn else w

    if args.json:
        print(render_json(report, root, check_names))
    else:
        print(render_text(report, root, check_names, base_status, sidecar_warn, source_empty))
    # A fixture that must be able to fail -- if it does NOT match
    # (compute_run_defects), the run still completes (numbers are
    # printed) but the exit code is no longer a bare 0.
    return 1 if compute_run_defects(report) else 0


if __name__ == "__main__":
    sys.exit(main())
