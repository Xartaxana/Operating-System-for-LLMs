# Boot Sequence

The repository is the only source of truth.

When starting a new conversation:

1. Read README.md.
2. Read PROJECT_CHARTER.md.
3. Read PROJECT_PHILOSOPHY.md.
4. Read ANTI_GOALS.md.
5. Read SYSTEM_PROMPT.md.
6. Read DECISIONS.md.
7. Read MEMORY_ARCHITECTURE.md.
8. Read ARCHITECTURE.md.
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
