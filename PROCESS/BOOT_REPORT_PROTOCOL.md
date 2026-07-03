# Boot Report Protocol

## Purpose

Every new LLM session must produce the same structured report after executing BOOT.md.

## Boot Report Template

```
BOOT REPORT

Repository Loaded: YES/NO

Constitution Loaded: YES/NO

Decisions Loaded: YES/NO

Current Context Loaded: YES/NO

Current Phase:

Current Objective:

Next Required Action:

Confidence:
```

## Rules

1. The very first visible output of a new session is an announcement
   that the boot sequence is starting (one line, e.g. "Executing
   BOOT.md"), before any file is read.
2. The Boot Report is emitted as a separate block immediately after
   the BOOT.md documents are loaded — before any reasoning about,
   or execution of, the current task.
3. The report must be generated before proposing new work.

Rationale for 1–2 (added 2026-07-03): a session that starts with a
silent series of file reads buries the report in tool noise; the
operator could not tell whether context recovery had happened.
