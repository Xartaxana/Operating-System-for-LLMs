# Boot Sequence

The repository is the only source of truth. If repository contents
conflict with chat history, the repository always wins.

Note: the Claude Code harness auto-loads CLAUDE.md (routing policy;
D-0041 — delegation is opt-in, so the policy must precede any task).
That auto-load is NOT a boot.

Memory is layered (MEMORY_ARCHITECTURE.md). Only two layers load at
boot, because boot context is paid (D-0038):

- **Layer A — ORIENTATION** (stable: the project's idea, architecture
  and goals — what every session must not forget). Small, always loaded.
- **Layer B — STATE** (the current in-flight picture — where we are and
  what is queued; the source of the Boot Report).

Everything else — the decision log, the delegation table, the
closed-phase roadmap, and the deep documents — is REFERENCE, point-read
ON DEMAND by pointer, never loaded at boot.

When starting a new conversation, read Layer A then Layer B:

## Layer A — Orientation (always)

If this session's SessionStart output already includes a
`--- BOOT LAYER A INJECTED (D-0103 hybrid) ...` block (verbatim
content of the five files below, closed by a `--- END BOOT LAYER A: N
files, N lines, N bytes emitted ---` line), Layer A is ALREADY in your
context — do not re-read the five files, that is the double payment
the injection exists to remove (D-0104). Reading a file anyway is only
warranted if the closing line is missing (the block was truncated) or
that file is shown as `[missing: ...]` (it was not printed).

If the block is NOT present (older/broken hook, a deployment not yet
carrying D-0104's hybrid delivery, or a manual boot outside the
harness), read the five files yourself, in order:

1. Read README.md.
2. Read PROJECT_CHARTER.md.
3. Read ANTI_GOALS.md.
4. Read PROJECT_PHILOSOPHY.md.
5. Read ARCHITECTURE_BOOT.md.

(ARCHITECTURE_BOOT.md is the condensed operative core, D-0067; the full
specification ARCHITECTURE.md is point-read on demand.)

## Layer B — State (for the Boot Report)

6. Read CURRENT_CONTEXT.md.

## Reference — NOT loaded at boot; point-read on demand

- DECISIONS.md — decision index (full texts in docs/DECISIONS_FULL.md).
- DELEGATION_TABLE.md — tier cost/value table and statuses.
- ROADMAP.md — phases and gates (all closed; the standing phase-
  transition procedure lives here).
- WHITE_PAPER.md, docs/, PROCESS/, docs/task_reports/ — deep documents.

After loading Layer A and Layer B, produce a Boot Report per
PROCESS/BOOT_REPORT_PROTOCOL.md:

- summarize the current state;
- identify the current milestone;
- identify the next objective;
- then STOP and wait for the operator's explicit confirmation.

Boot recovery is not work authorization: do not start the next task
(reading additional files for implementation, writing code) until the
operator confirms.
