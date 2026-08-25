"""tools/test_warn_messages.py -- machine check of warn-text FORM (C-K4,
synced from HQ's tools/test_warn_messages.py) for the node-C warn
layers registered in tools/warn_layers.json, PARAMETRIZED BY the
layers' own carrier modules (read via getattr/call, not copied as
literals into this file's body).

OWNERSHIP NOTE (this port's own adaptation, documented): this file's
owns is D5 (search_control_gate.py, negative_lint.py,
claim_control_gate.py) -- but the battery below is, by construction,
PARAMETRIZED ACROSS every node-C hook (owns_gate.py, journal_echo.py,
hygiene_gate.py included), same as HQ's own file. This node's WITNESS
is narrowed to `-k` on the three D5 gates only (spec: "in D5's witness,
run warn_messages -k on your own files only -- the full run is the
coordinator's job at batch merge, not this node's green"). Entries for
the other three carriers are still written here (accurately, against
their CURRENT toolkit text) so the file is immediately useful once
those nodes' own diffs land, but their correctness is NOT this node's
witness.

REGISTRY-DRIVEN SCOPE ADAPTATION -- RESOLVED: QUOTED_OWNS, NOTES_LEN,
R3_MIRROR and FRESHNESS have now been registered in
tools/warn_layers.json (16 entries total; this registry's own
ESCALATION entry still deliberately keeps its own name rather than
HQ's R6-MIRROR rename, per its "_note" field -- unchanged by this
node). CD_NON_ROOT was considered as a SEPARATE registry entry and
REJECTED (empirically checked against both hygiene_gate.py's own
wiring and HQ's own registry, command hygiene point 6): MSG_CD_NON_ROOT_WARN
is appended to the SAME `warn_reasons` list every other warn-branch
hygiene text is, and gets wrapped by the SAME "Command hygiene (WARN,
does not block): " prefix at the wire level (hygiene_gate.py:
`warn_reasons.append(MSG_CD_NON_ROOT_WARN)`) -- it is not an
independently-prefixed wire text, so it belongs under the single
HYGIENE registry entry (via the wrapped-form alias, a PRE-EXISTING
registry gap this node does not fix -- see
test_c4_hygiene_registry_prefix_present below), not a new id. HQ's own
registry confirms this shape: no separate CD_NON_ROOT-class id exists
there either, only HYGIENE with an `aliases` entry for the wrapped
form.

VERB-CASE HONESTY (rule-of-three C-K4 check 1/4): a layer's expected
verb SET is a plain enumeration of what its CURRENT text actually
contains -- not a design decision about what it should contain. Node E
item 6 brought TIER_ECHO (mismatch/info), WITNESS_ECHO (warn_loud/
warn_stale) and ESCALATION to rule-of-three form (each now carries a
real imperative verb) -- these move from EXCLUDED into _VERB_CASES
below (were: no verb present at all, per this file's own D5-era
reading, now superseded). hygiene_gate.py's MSG_CD_NON_ROOT_WARN
received the same treatment (verb "invoke"), added to _VERB_CASES too.
QUOTED_OWNS/NOTES_LEN/R3_MIRROR/FRESHNESS already carried an
imperative verb in their CURRENT toolkit text at registration time
(checked directly against each formatter before writing their cases
below, the same discipline this file's own header already commits to)
-- no text edit was needed for those four.

Run:  python -m pytest tools/test_warn_messages.py -q
Narrowed (this node's witness): python -m pytest tools/test_warn_messages.py -q -k "NEGATIVE_LINT or NEGATIVE_CLAIM or SEARCH_RETURNED_NOTHING"
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

WARN_LAYERS_PATH = TOOLS_DIR / "warn_layers.json"


def _load_module(msg_name: str, live_name: str, alias: str):
    """f61-form (same K-class pattern the sibling test_*_md.py files in
    this owns already carry): a _msg.py sibling, IF it exists, else the
    live file. No _msg.py sibling exists in this template today for any
    of the six carriers -- always resolves to the live file."""
    sib = TOOLS_DIR / msg_name
    path = sib if sib.exists() else TOOLS_DIR / live_name
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owns_gate = _load_module("owns_gate_msg.py", "owns_gate.py", "owns_gate_wm")
journal_echo = _load_module("journal_echo_msg.py", "journal_echo.py", "journal_echo_wm")
negative_lint = _load_module("negative_lint_msg.py", "negative_lint.py", "negative_lint_wm")
claim_control_gate = _load_module(
    "claim_control_gate_msg.py", "claim_control_gate.py", "claim_control_gate_wm"
)
search_control_gate = _load_module(
    "search_control_gate_msg.py", "search_control_gate.py", "search_control_gate_wm"
)
hygiene_gate = _load_module("hygiene_gate_msg.py", "hygiene_gate.py", "hygiene_gate_wm")
dispatch_gate = _load_module("dispatch_gate_msg.py", "dispatch_gate.py", "dispatch_gate_wm")


@pytest.fixture(scope="session")
def registry():
    with WARN_LAYERS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _layer(registry_data, layer_id):
    for layer in registry_data["layers"]:
        if layer["id"] == layer_id:
            return layer
    raise KeyError(layer_id)


# ---------------------------------------------------------------------
# Render CURRENT texts -- each calls a function/constant FROM the
# module (not a copy of the text in this file's own body, C-K4 literal
# requirement).
# ---------------------------------------------------------------------


def _render_owns_overlap() -> str:
    records = [
        {
            "ts": "2026-08-25T10:00:00",
            "session_key": "other-session",
            "cwd": "D:/repo",
            "description": "another dispatch",
            "owns": ["tools/x.py"],
        }
    ]
    grouped = owns_gate._find_overlaps(["tools/x.py"], records, "this-session")
    return owns_gate._format_overlap_context(grouped)


def _render_tier_echo(kind: str) -> str:
    if kind == "mismatch":
        event = (2, "mismatch", "sonnet", {"claude-opus-4-8": 1})
    else:
        event = (2, "info", "sonnet", {"claude-fable-1": 1, "claude-sonnet-5": 1})
    return journal_echo._format_tier_line(event, ascii_only=False)


def _render_witness_echo(kind: str) -> str:
    if kind == "warn_loud":
        event = ("warn_loud", 2, "pytest -q", "2026-08-25T10:00:00")
    elif kind == "warn_stale":
        event = ("warn_stale", 2, "2026-08-25T10:00:00", "2026-08-24T09:00:00")
    else:
        event = ("warn_soft", 2)
    return journal_echo._format_witness_line(event, ascii_only=False)


def _render_ts_drift(kind: str) -> str:
    delta = 5 if kind == "future" else -5
    return journal_echo._format_ts_drift_line((2, kind, delta))


def _render_escalation() -> str:
    event = (2, "trigger", "t-042", "2 of 2")
    return journal_echo._format_escalation_line(event, ascii_only=False)


def _render_negative_lint() -> str:
    return negative_lint.format_warning([(3, "example negative line")])


def _render_negative_claim() -> str:
    return claim_control_gate.MSG_TEMPLATE.format(tokens="x.py")


def _render_search_returned_nothing() -> str:
    return search_control_gate.MSG


def _render_hygiene(name: str) -> str:
    return getattr(hygiene_gate, name)


def _render_hygiene_wrapped() -> str:
    # same concatenation pattern decide() itself uses for the warn-only
    # branch (hygiene_gate.py, warn_reasons path) -- prefix check below.
    return "Command hygiene (WARN, does not block): " + hygiene_gate.MSG_CD_PREFIX


def _render_hygiene_cd_non_root_wrapped() -> str:
    # MSG_CD_NON_ROOT_WARN goes through the SAME
    # warn_reasons -> wrapped-prefix path as MSG_CD_PREFIX above (see
    # the module docstring, "REGISTRY-DRIVEN SCOPE ADAPTATION --
    # RESOLVED") -- not an independently-prefixed wire text.
    return "Command hygiene (WARN, does not block): " + hygiene_gate.MSG_CD_NON_ROOT_WARN


def _render_quoted_owns() -> str:
    return owns_gate.QUOTED_OWNS_WARN_MESSAGE


def _render_notes_len() -> str:
    event = (2, "accepted", 900, 800)
    return journal_echo._format_notes_len_line(event)


def _render_r3_mirror(kind: str) -> str:
    if kind == "phantom_basis":
        event = (2, "phantom_basis", "t-042", None)
    else:
        event = (2, "no_input", "t-042", None)
    return journal_echo._format_r3_line(event, ascii_only=False)


def _render_freshness() -> str:
    # Same firing shape test_dispatch_gate_md.py's own
    # test_freshness_class_v_within_bounds_no_warn uses to trigger a
    # REAL freshness_warn() hit: an anchor on an EXISTING file
    # (dispatch_gate.py itself) with a line number far past its actual
    # length.
    repo_root = str(TOOLS_DIR.parent)
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "Given: tools/dispatch_gate.py:9999999.",
        },
        "cwd": repo_root,
    }
    return dispatch_gate.freshness_warn(payload)


def _render_write_quoted() -> str:
    # A write signal (WRITE_INDICATORS_RE match "write file") whose ONLY
    # occurrence sits inside a blockquote, with no given/owns manifest
    # marker anywhere in the prompt -- see write_quoted_warn's own
    # docstring for the exact fire condition.
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "See example:\n> write file example.py\n",
        },
    }
    return dispatch_gate.write_quoted_warn(payload)


def _render_dod_quoted() -> str:
    # A DoD marker whose ONLY occurrence sits inside a blockquote.
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "See example:\n> DoD marker inside a quote.\n",
        },
    }
    return dispatch_gate.dod_quoted_warn(payload)


def _render_manifest_quoted() -> str:
    # A "given" manifest marker whose ONLY occurrence sits inside a
    # blockquote.
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "See example:\n> Given: some data here.\n",
        },
    }
    return dispatch_gate.manifest_quoted_warn(payload)


def _render_journal_echo_base() -> str:
    return journal_echo.build_context(["line 3: example defect"], ascii_only=False)


# ---------------------------------------------------------------------
# C-K4 (1/4): imperative verb from a CLOSED set. The set is this
# test's OWN mechanical construction (a per-layer expected-verb list --
# exactly what this node's builder wrote into the texts it touched, or
# accurately reads in texts it did not touch -- not a design decision),
# not a copy of the whole message body. Node E item 6 brought
# TIER_ECHO/WITNESS_ECHO(loud/stale)/ESCALATION/MSG_CD_NON_ROOT_WARN to
# rule-of-three form -- these move IN here from the excluded set the
# D5-era docstring used to carry (see module docstring, "VERB-CASE
# HONESTY").
# ---------------------------------------------------------------------

_VERB_CASES = [
    ("OWNS_OVERLAP", _render_owns_overlap, {"serialize", "split"}),
    ("BLIND_OWNS", lambda: owns_gate.BLIND_OWNS_WARN_MESSAGE, {"check"}),
    ("QUOTED_OWNS", _render_quoted_owns, {"move"}),
    ("NOTES_LEN", _render_notes_len, {"move", "keep"}),
    ("R3_MIRROR/no_input", lambda: _render_r3_mirror("no_input"), {"close"}),
    ("R3_MIRROR/phantom_basis", lambda: _render_r3_mirror("phantom_basis"), {"close"}),
    ("FRESHNESS", _render_freshness, {"re-read", "update", "drop", "keep"}),
    ("WRITE_QUOTED", _render_write_quoted, {"verify"}),
    ("DOD_QUOTED", _render_dod_quoted, {"verify"}),
    ("MANIFEST_QUOTED", _render_manifest_quoted, {"verify"}),
    ("TIER_ECHO/mismatch", lambda: _render_tier_echo("mismatch"), {"check", "fix", "relaunch"}),
    ("TIER_ECHO/info", lambda: _render_tier_echo("info"), {"check"}),
    ("WITNESS_ECHO/warn_loud", lambda: _render_witness_echo("warn_loud"), {"re-run", "confirm"}),
    ("WITNESS_ECHO/warn_stale", lambda: _render_witness_echo("warn_stale"), {"re-run", "confirm"}),
    ("WITNESS_ECHO/warn_soft", lambda: _render_witness_echo("warn_soft"), {"verify"}),
    ("TS_DRIFT/future", lambda: _render_ts_drift("future"), {"read"}),
    ("TS_DRIFT/stale", lambda: _render_ts_drift("stale"), {"read"}),
    ("ESCALATION", _render_escalation, {"escalate", "append"}),
    ("NEGATIVE_LINT", _render_negative_lint, {"add", "double-check"}),
    ("NEGATIVE_CLAIM", _render_negative_claim, {"run"}),
    ("SEARCH_RETURNED_NOTHING", _render_search_returned_nothing, {"run"}),
    ("HYGIENE/MSG_CD_PREFIX", lambda: _render_hygiene("MSG_CD_PREFIX"), {"invoke"}),
    ("HYGIENE/MSG_REDIRECT_STDERR", lambda: _render_hygiene("MSG_REDIRECT_STDERR"), {"drop"}),
    ("HYGIENE/MSG_PYTHON_DASH_C", lambda: _render_hygiene("MSG_PYTHON_DASH_C"), {"use"}),
    ("HYGIENE/MSG_CD_NON_ROOT_WARN", _render_hygiene_cd_non_root_wrapped, {"invoke"}),
]


def _contains_imperative_verb(text: str, verbs: set) -> bool:
    """Closed set -- case-insensitive substring search for ANY verb in
    the set (the set is layer-specific -- a cheap form, not a claim
    about the whole language's morphology)."""
    low = text.lower()
    return any(v.lower() in low for v in verbs)


@pytest.mark.parametrize(
    "name,render,verbs", _VERB_CASES, ids=[c[0] for c in _VERB_CASES]
)
def test_c4_imperative_verb_present(name, render, verbs):
    text = render()
    assert _contains_imperative_verb(text, verbs), f"{name}: {text!r} carries none of {verbs}"


def test_verb_checker_negative_control_text_without_verb_fails():
    """C-K4 literally: "a text with no verb -> the test goes red."
    Checks the CHECKER itself (not a real constant) -- a synthetic
    string with none of the set's verbs must give False."""
    bad_text = "path not found, state unknown, the registry stays silent"
    assert not _contains_imperative_verb(bad_text, {"check", "fix", "run", "verify"})


def test_verb_checker_positive_control_text_with_verb_passes():
    # positive control in the pair (command hygiene point 6) -- the
    # same checker, same text shape, a verb present.
    good_text = "path not found \u2014 check the owns line's form"
    assert _contains_imperative_verb(good_text, {"check", "fix"})


# ---------------------------------------------------------------------
# C-K4 (2/4): length within budget -- WARN_TEXT_BUDGET_CHARS=550 (the
# same numeric budget HQ's own node landed; carried here since this
# node ports the SAME mechanical check, not a fresh measurement of this
# template's own texts -- see the boundary tests below for the ratchet
# itself, independent of any live constant).
# ---------------------------------------------------------------------

WARN_TEXT_BUDGET_CHARS = 550

# The length-budget check runs over EVERY rendered sub-case this file
# knows how to render. Every sub-case this file
# renders now carries a verb (TIER_ECHO/WITNESS_ECHO-loud-stale/
# ESCALATION/MSG_CD_NON_ROOT_WARN moved INTO _VERB_CASES above) -- the
# "superset" extra list is now empty, kept as an explicit empty tail
# for the next sub-case that turns out verb-less, rather than deleted
# (documents the pattern still exists, is not simply unused).
_ALL_RENDER_CASES = _VERB_CASES + [
    ("JOURNAL_ECHO_BASE", _render_journal_echo_base),
]
# Normalize each entry to (name, render) -- _VERB_CASES entries carry a
# third (verbs) element the length check does not need.
_ALL_RENDER_CASES = [(c[0], c[1]) for c in _ALL_RENDER_CASES]


@pytest.mark.parametrize(
    "name,render", _ALL_RENDER_CASES, ids=[c[0] for c in _ALL_RENDER_CASES]
)
def test_c4_length_within_budget(name, render):
    text = render()
    assert len(text) <= WARN_TEXT_BUDGET_CHARS, (
        f"{name}: {len(text)} chars > budget {WARN_TEXT_BUDGET_CHARS} -- {text!r}"
    )


def _within_length_budget(text: str) -> bool:
    """The budget predicate itself -- factored out so the boundary
    tests below check the EXACT SAME logic test_c4_length_within_budget
    applies to the live battery (not a duplicate comparison)."""
    return len(text) <= WARN_TEXT_BUDGET_CHARS


def _synthetic_text_of_length(length: int) -> str:
    """Boundary helper (rule 6a: a limit needs a test AT and BEYOND it)
    -- a SYNTHETIC string of the given length; no live constant is
    corrupted to probe the boundary."""
    return "x" * length


def test_c4_length_budget_boundary_at_550_passes():
    text = _synthetic_text_of_length(WARN_TEXT_BUDGET_CHARS)
    assert len(text) == 550
    assert _within_length_budget(text) is True


def test_c4_length_budget_boundary_551_beyond_fails():
    text = _synthetic_text_of_length(WARN_TEXT_BUDGET_CHARS + 1)
    assert len(text) == 551
    assert _within_length_budget(text) is False


# ---------------------------------------------------------------------
# C-K4 (3/4): registry prefix present -- each layer's registry
# "literal" byte-exact at the START of its rendered text.
# ---------------------------------------------------------------------

_PREFIX_CASES = [
    ("OWNS_OVERLAP", _render_owns_overlap),
    ("BLIND_OWNS", lambda: owns_gate.BLIND_OWNS_WARN_MESSAGE),
    ("QUOTED_OWNS", _render_quoted_owns),
    ("NOTES_LEN", _render_notes_len),
    ("R3_MIRROR", lambda: _render_r3_mirror("no_input")),
    ("FRESHNESS", _render_freshness),
    ("WRITE_QUOTED", _render_write_quoted),
    ("DOD_QUOTED", _render_dod_quoted),
    ("MANIFEST_QUOTED", _render_manifest_quoted),
    ("TIER_ECHO", lambda: _render_tier_echo("mismatch")),
    ("WITNESS_ECHO", lambda: _render_witness_echo("warn_loud")),
    ("TS_DRIFT", lambda: _render_ts_drift("future")),
    ("ESCALATION", _render_escalation),
    ("NEGATIVE_LINT", _render_negative_lint),
    ("NEGATIVE_CLAIM", _render_negative_claim),
    ("SEARCH_RETURNED_NOTHING", _render_search_returned_nothing),
    ("JOURNAL_ECHO_BASE", _render_journal_echo_base),
]


@pytest.mark.parametrize("layer_id,render", _PREFIX_CASES, ids=[c[0] for c in _PREFIX_CASES])
def test_c4_registry_prefix_present(registry, layer_id, render):
    literal = _layer(registry, layer_id)["literal"]
    text = render()
    assert text.startswith(literal), f"{layer_id}: {text[:80]!r} does not start with {literal!r}"


def test_c4_hygiene_registry_prefix_present(registry):
    # HYGIENE's registry "literal" is the UNWRAPPED prefix ("Command
    # hygiene: ", the deny-branch form); the warn-only branch wraps
    # with a DIFFERENT, longer prefix (see _render_hygiene_wrapped).
    # This template's registry HYGIENE entry carries no "aliases" for
    # the wrapped form (a registry gap -- node C4's owns, reported, not
    # fixed here) -- checked directly against the module SOURCE instead
    # of registry aliases, same as test_adversarial_hygiene_both_
    # alias_forms_alive_in_module_source below.
    layer = _layer(registry, "HYGIENE")
    wrapped = _render_hygiene_wrapped()
    assert wrapped.startswith("Command hygiene (WARN, does not block): ")
    assert layer["literal"] == "Command hygiene: "


# ---------------------------------------------------------------------
# C-K4 (4/4): no literal overlap across the FULL registry (not just
# this node's six carriers -- a registry-wide invariant). Does not
# require importing any node-C module.
# ---------------------------------------------------------------------


def _all_literal_strings(registry_data) -> list:
    out = []
    for layer in registry_data["layers"]:
        out.append((layer["id"], layer["literal"]))
        for alias in layer.get("aliases") or []:
            out.append((layer["id"] + ":alias", alias))
    return out


def test_c4_no_literal_overlap_across_full_registry(registry):
    strings = _all_literal_strings(registry)
    for i, (id_a, lit_a) in enumerate(strings):
        for id_b, lit_b in strings[i + 1 :]:
            if id_a.split(":")[0] == id_b.split(":")[0]:
                continue  # same layer and its own alias -- not an overlap
            assert lit_a not in lit_b and lit_b not in lit_a, (
                f"{id_a} ({lit_a!r}) overlaps {id_b} ({lit_b!r})"
            )


# ---------------------------------------------------------------------
# C-K3 sweep (D-0100 class): per node-C registry entry -- a verdict
# "split / does not need splitting -- why". Machine-pinned COUNT of
# sub-cases -- no prose "the rest were checked" substitute, here or in
# the report.
# ---------------------------------------------------------------------

_CK3_SPLIT_VERDICTS = {
    "OWNS_OVERLAP": 1,  # one code path, one action -- no split needed
    "BLIND_OWNS": 1,
    "QUOTED_OWNS": 1,  # one code path, no split needed
    "NOTES_LEN": 1,
    "R3_MIRROR": 2,  # no_input/phantom_basis -- already split
    "TIER_ECHO": 2,  # mismatch/info -- already split (a kind branch)
    "WITNESS_ECHO": 3,  # warn_loud/warn_stale/warn_soft -- already split
    "TS_DRIFT": 2,  # future/stale -- already split
    "ESCALATION": 1,
    "NEGATIVE_LINT": 1,
    "NEGATIVE_CLAIM": 1,
    "SEARCH_RETURNED_NOTHING": 1,
    "HYGIENE": 4,  # MSG_CD_PREFIX/MSG_REDIRECT_STDERR/MSG_PYTHON_DASH_C/MSG_CD_NON_ROOT_WARN
    "JOURNAL_ECHO_BASE": 1,  # one code path (build_context), no split needed
}


def test_c3_split_verdict_enumeration_covers_all_node_c_layers(registry):
    node_c_carriers = {
        "tools/owns_gate.py",
        "tools/journal_echo.py",
        "tools/negative_lint.py",
        "tools/claim_control_gate.py",
        "tools/search_control_gate.py",
        "tools/hygiene_gate.py",
    }
    node_c_layer_ids = {
        layer["id"] for layer in registry["layers"] if layer["carrier"][0] in node_c_carriers
    }
    assert node_c_layer_ids == set(_CK3_SPLIT_VERDICTS.keys())
    # 14 (13 + JOURNAL_ECHO_BASE, newly registered in
    # tools/warn_layers.json). FRESHNESS/WRITE_QUOTED/DOD_QUOTED/
    # MANIFEST_QUOTED are also newly registered but their carrier is
    # tools/dispatch_gate.py, NOT a node_c_carrier, so they do not count
    # here.
    assert len(node_c_layer_ids) == 14


# ---------------------------------------------------------------------
# Adversarial battery (narrowed to what this template's current tree
# can actually verify true -- see module docstring for the ownership
# split; a full battery mirroring HQ's own is the coordinator's job at
# batch merge, not this node's witness).
# ---------------------------------------------------------------------


def test_adversarial_emoji_in_dynamic_part_does_not_crash_and_keeps_static_prefix():
    # emoji/surrogates in the DYNAMIC part (declared_word) -- the
    # sanitizer must not crash, the static prefix must stay intact.
    event = (2, "mismatch", "sonnet\U0001F600", {"claude-opus-4-8": 1})
    text = journal_echo._format_tier_line(event, ascii_only=False)
    assert text.startswith("TIER ECHO: line 2")


def test_adversarial_ascii_only_channel_sanitizes_non_ascii_dynamic_part():
    # a non-UTF8 Windows console -- ascii_only=True must not raise and
    # must replace non-ASCII in the DYNAMIC part with "?"; the static
    # part stays as-is.
    event = ("warn_loud", 2, "pytest -q caf\u00e9", "2026-08-25T10:00:00")
    text = journal_echo._format_witness_line(event, ascii_only=True)
    assert text.startswith("WITNESS ECHO: line 2")
    assert "caf\u00e9" not in text


def test_adversarial_hygiene_both_alias_forms_alive_in_module_source():
    # HYGIENE -- two wrapping forms (deny vs warn-only branch), both
    # must be alive in the carrier source; this node did not touch the
    # wrapping code in hygiene_gate.py, only MSG_*-constants elsewhere
    # in this template's own three gates -- regression pin.
    source = (TOOLS_DIR / "hygiene_gate.py").read_text(encoding="utf-8")
    assert "Command hygiene: " in source
    assert "Command hygiene (WARN, does not block): " in source


def test_adversarial_no_literal_carries_open_brace():
    # "a literal with `{`" would break naive str.format() callers
    # downstream -- pin on the registry's own already-encoded literals
    # (this node did not change any of them).
    with WARN_LAYERS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    for layer in data["layers"]:
        assert "{" not in layer["literal"], layer["id"]


def test_adversarial_tier_segment_boundary_5_vs_6_still_caps():
    # MAX_TIER_LINES=5 -- an inherited boundary (not introduced by this
    # node), pinned to prove this node's own text edits (none touched
    # journal_echo.py) did not disturb build_tier_segment's cap: 5
    # events -> all fit, 6 -> "+1 more".
    events5 = [(i, "info", "sonnet", {"claude-sonnet-5": 1}) for i in range(1, 6)]
    events6 = [(i, "info", "sonnet", {"claude-sonnet-5": 1}) for i in range(1, 7)]
    seg5 = journal_echo.build_tier_segment(events5, ascii_only=False)
    seg6 = journal_echo.build_tier_segment(events6, ascii_only=False)
    assert seg5.count("TIER ECHO") == 5
    assert "more" not in seg5
    assert seg6.count("TIER ECHO") == 5
    assert "+1 more" in seg6


# ---------------------------------------------------------------------
# Positional edge: inputs on which a layer stays SILENT, identical
# before/after this node's text-only edits -- checked by non-emptiness,
# not by text.
# ---------------------------------------------------------------------


def test_positional_empty_tier_events_still_silent():
    assert journal_echo.build_tier_segment([], ascii_only=False) == ""


def test_positional_empty_witness_events_still_silent():
    assert journal_echo.build_witness_segment([], ascii_only=False) == ""


def test_positional_empty_ts_drift_events_still_silent():
    assert journal_echo.build_ts_drift_segment([], ascii_only=False) == ""


def test_positional_decide_text_without_negatives_stays_silent():
    # This node's own gate (negative_lint.py) -- the WARN_PREFIX_TEMPLATE
    # edit must not have moved the silent-path decision: text with no
    # negative marker at all renders nothing.
    exit_code, output = negative_lint.decide(
        {"tool_name": "Task", "tool_response": "Everything found and verified, all present."}
    )
    assert exit_code == 0
    assert output is None
