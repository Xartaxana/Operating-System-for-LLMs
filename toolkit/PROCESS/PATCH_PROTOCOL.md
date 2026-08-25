# Patch Protocol

Status: fallback mechanism.

Direct git commits are the standard way to change the repository when
the LLM has repository access. A patch/diff file is used only in
environments without such access.

Whether applied as a commit or a patch, every change should:

1. Solve one conceptual problem.
2. Preserve repository consistency.
3. Update affected documentation.
4. Leave the repository in a self-contained state.
5. Avoid hidden knowledge.

## Policy-carrier patches

A patch touching a policy carrier this kit ships (CLAUDE.md, an
`.claude/agents/*.md` role file, a `PROCESS/*.md` document covered by
`tools/install_parity_anchors.json`) is not closed until it produces
an install-parity record: the closing step of an upgrade (the
onboarding skill's Upgrade mode, step 7) runs
`tools/install_parity.py --check` against the FINAL, committed tree
and writes "Install parity: ..." as its own record line — in the
adoption ledger's "Kit snapshot revision" note, or the upgrade commit
message. No install-parity record for a patched policy carrier means
the patch has not actually been verified to have landed on the host's
tree; `tools/wiring_check.py`'s notices channel (K12, non-blocking)
surfaces a ledger revision with no matching record as a WARN, not a
block -- the record itself is the closing evidence this protocol
requires, not the WARN's absence.
