"""One-time key-run for W2c-1 (CLAUDE.md diet), R11(l) three-property script.

Keys quoted VERBATIM from docs/tasks/2026-08-19_w2c-keys.md #1, BEFORE the
run. Fold contract: {space,tab,CR,LF}+ -> single space; '|' is NOT folded
(mirrors tools/escape_check.py's _fold_whitespace()).

Usage:
    python key_run_w2c1.py <path-to-CLAUDE.md> <path-to-delegation.config.yaml>

Exit 0 and "KEY RUN OK" on success; exit 1 with one diagnostic line per
violation otherwise. A run with a fully empty A/A-prime key list is treated
as a usage error (fail-closed) -- not applicable here since the key lists
below are always non-empty.
"""
import re
import sys

WS_RE = re.compile(r"[ \t\r\n]+")


def fold(s):
    return WS_RE.sub(" ", s)


def read(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8")


# A / A-prime keys: must occur >=1 time in folded CLAUDE.md text.
A_KEYS = {
    "c1-1": "This repo is the reference (dogfooding) deployment",
    "c1-2": "never invent project state \u2014 retrieve it from the repository",
    "c1-3": "the repository overrides chat",
    "c1-4": "This file holds only what must ALWAYS be in context",
    "c1-5": "Full state recovery is BOOT.md",
    "c1-6": "an amendment to a rule with a registry block is a ROW in that registry",
    "c1-7": "Breach \u2192 boot-diet, CLAUDE layer",
    "c2-1": "are accounting vocabulary, never rule words",
    "c2-2": 'ARCHITECTURE.md "Two Vocabularies"',
    "c2-3": "Policy rules speak ONLY these function names",
    "c2-4": "the function\u2192model binding is a deployment property",
    "c2-5": "defaulting to fable when the file is absent",
    "c2-6": "A RESERVE tier sits ABOVE the Lead binding",
    "c2-7": "summoned only by the operator's word for the hardest cases",
    "c5-1": "Enforced at TWO points",
    "c5-2": "tools/journal_validator.py",
    "c5-3": "re-read the journal tail immediately before",
    "c5-4": "never reuse a remembered id",
    "c5-6": "a missed event is fixed by a retro pair NOW",
    "c5-7": "inserting lines into the past is forbidden",
    "c5-8": "the SessionStart hook reads ONLY this token",
    "c5-9": "never write the literal form with a live id in prose",
    "c5-10": "Closure is reader-specific, not one fact",
    "c5-11": 'or "judge" on a leaf-class dispatch',
    "c6-1": "While degraded",
    "c6-2": "naming cause and scope",
    "c6-3": "coordination and authorized tasks \u2014 yes",
    "c6-4": "table statuses and gates \u2014 no",
    "c6-5": "new DECISIONS \u2192 the Lead queue",
    "c6-6": "acceptance per the Role \u2260 tier matrix",
    "c6-7": "Return is the DEFAULT at the task/session boundary",
    "c6-8": "diffs of ALL repos touched by the session, D-0044",
    "c6-9": "an empty window is noted explicitly",
    "c6-10": "Triggers: refusal of the Lead-binding model",
    "c6-11": "check your actual model by the last visible signal",
    "c6-12": "is a full Lead with margin \u2014 no window needed",
    "c6-13": "a visible ascent is by itself PROOF of a window",
    "c6-14": "A degradation crossing the session boundary must be the journal's last event",
    "c7-1": "the verdict sits at the END of an append-only entry",
    "c7-2": "valid only after reading THROUGH that entry's status line",
    "c7-3": "grepping the status FIELD itself",
    "c7-4": "the presence of the entry or of its header inside a read window is NOT a check",
    "c7-5": "an empty result is reported only after a positive control of the call",
    "c7-6": "a control with a different pattern proves the pipe, not absence",
    "c7-7": 'unverified \u2014 mark explicitly "estimate, not verified"',
}

# R keys: must occur 0 times in folded CLAUDE.md text.
R_KEYS = {
    "c1-R": "the pilot is D:\\AO3_tests",
    "c2-R": "never used in rules",
    "c5-5": "A repeat `delegated` on a CLOSED task is forbidden",
    "c7-R": "Append-only registries put the verdict at the END of a multi-section entry",
}

# c6-R: 'stateDiagram-v2' must be absent from the Lead-degradation section
# range, present elsewhere in the file (Journal section) as positive control.
C6_R_KEY = "stateDiagram-v2"
DEGRADATION_HEADER = "## Lead degradation"

# P key: must occur >=1 time in delegation.config.yaml.
P_KEYS = {
    "c1-8": "deploys:",
}


def slice_degradation_section(text):
    """Return the raw (unfolded) text of the '## Lead degradation' section:
    from its header line up to (not including) the next '## ' H2 header, or
    EOF. Returns None if the header is not found."""
    idx = text.find(DEGRADATION_HEADER)
    if idx == -1:
        return None
    rest = text[idx + len(DEGRADATION_HEADER):]
    next_h2 = re.search(r"\n## ", rest)
    if next_h2:
        return text[idx: idx + len(DEGRADATION_HEADER) + next_h2.start()]
    return text[idx:]


def run(claude_path, deleg_path):
    violations = []

    claude_text = read(claude_path)
    claude_folded = fold(claude_text)
    deleg_text = read(deleg_path)
    deleg_folded = fold(deleg_text)

    for key_id, phrase in A_KEYS.items():
        if fold(phrase) not in claude_folded:
            violations.append("A-key %s NOT FOUND (expected >=1): %r" % (key_id, phrase))

    for key_id, phrase in R_KEYS.items():
        count = claude_folded.count(fold(phrase))
        if count != 0:
            violations.append("R-key %s FOUND %d time(s) (expected 0): %r" % (key_id, count, phrase))

    for key_id, phrase in P_KEYS.items():
        if fold(phrase) not in deleg_folded:
            violations.append("P-key %s NOT FOUND in delegation.config.yaml (expected >=1): %r" % (key_id, phrase))

    # c6-R: positive control first (mechanism liveness), then the negative
    # scoped to the degradation section.
    total_count = claude_folded.count(fold(C6_R_KEY))
    if total_count == 0:
        violations.append(
            "c6-R positive control FAILED: %r not found ANYWHERE in file "
            "(mechanism broken, negative below is not trustworthy)" % C6_R_KEY
        )
    else:
        deg_section = slice_degradation_section(claude_text)
        if deg_section is None:
            violations.append("c6-R: degradation section header not found: %r" % DEGRADATION_HEADER)
        else:
            deg_folded = fold(deg_section)
            deg_count = deg_folded.count(fold(C6_R_KEY))
            if deg_count != 0:
                violations.append(
                    "c6-R FOUND %d time(s) inside the degradation section "
                    "(expected 0): %r" % (deg_count, C6_R_KEY)
                )

    return violations


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: key_run_w2c1.py <CLAUDE.md> <delegation.config.yaml>\n")
        return 2
    violations = run(argv[1], argv[2])
    if violations:
        sys.stderr.write("KEY RUN FAILED (%d):\n" % len(violations))
        for v in violations:
            sys.stderr.write("  - %s\n" % v)
        return 1
    sys.stdout.write("KEY RUN OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
