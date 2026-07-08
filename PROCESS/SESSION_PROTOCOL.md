# Session Protocol

## Session Start

1. Connect the repository.
2. Follow BOOT.md.
3. Produce a Boot Report (PROCESS/BOOT_REPORT_PROTOCOL.md).
4. STOP; wait for the operator's confirmation before starting work.

## Session End

Before ending a session:

- Record new decisions.
- Update roadmap if necessary.
- Update architecture if necessary.
- Update current context; archive closed items to docs/task_reports/
  (D-0038).
- Commit directly to git (D-0026); produce a Patch only as fallback
  when repository access is unavailable (PROCESS/PATCH_PROTOCOL.md).
- Run the session-handoff check (.claude/skills/session-handoff/,
  D-0050): git clean and pushed in both repos, journal closed, boot
  budget measured, boot chain alive. Its report is the session's
  last output; the final commit+push is the session's last action.

No important knowledge should remain only inside chat history.
