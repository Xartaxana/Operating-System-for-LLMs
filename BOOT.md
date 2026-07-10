# Boot Sequence

The repository is the only source of truth.

Note: in Claude Code sessions the harness auto-loads CLAUDE.md
(routing policy; D-0041 — delegation is opt-in, so the policy must be
in context before any task). That auto-load is NOT a boot: full state
recovery is still this sequence, executed on the operator's request.

When starting a new conversation:

1. Read README.md.
2. Read PROJECT_CHARTER.md.
3. Read PROJECT_PHILOSOPHY.md.
4. Read ANTI_GOALS.md.
5. Read SYSTEM_PROMPT.md.
6. Read DECISIONS.md.
7. Read MEMORY_ARCHITECTURE.md.
8. Read ARCHITECTURE_BOOT.md (condensed operative core, D-0067;
   the full specification ARCHITECTURE.md is point-read on demand).
9. Read DELEGATION_TABLE.md.
10. Read ROADMAP.md.
11. Read CURRENT_CONTEXT.md.

After loading these documents, produce a Boot Report per
PROCESS/BOOT_REPORT_PROTOCOL.md:

- summarize the current state;
- identify the current milestone;
- identify the next objective;
- then STOP and wait for the operator's explicit confirmation.

Boot recovery is not work authorization: do not start the next task
(reading additional files for implementation, writing code) until the
operator confirms. Deep documents (WHITE_PAPER.md, docs/, PROCESS/,
docs/task_reports/) are loaded on demand, not at boot.

If repository contents conflict with chat history, the repository always wins.
