# Boot Report Protocol

## Purpose

Every new LLM session must produce the same structured report after executing BOOT.md.

## Boot Report Template

```
BOOT REPORT

Repository Loaded: YES/NO

Working Tree at Boot: CLEAN / DIRTY (n files) / UNPUSHED (n commits)

Orientation Loaded (Layer A): YES (injected) / YES (read) / NO

State Loaded (Layer B — CURRENT_CONTEXT): YES/NO

Current Phase:

Last Calibration:

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
4. After the report, STOP and wait for the operator's explicit
   confirmation before starting any task. Boot recovery is not work
   authorization; neither BOOT.md's queue nor an unblocked task in
   CURRENT_CONTEXT.md overrides this stop. SessionStart hook lines
   (BOOT BUDGET BREACH, OPEN DISPATCH, staleness flags) are the same
   class of signal: they feed the report's Next Required Action line,
   they do not authorize executing the flagged procedure before the
   report and the operator's word (precedent 2026-07-15: a session
   ran the boot-diet skill off the hook line before reporting).

5. Last Calibration = the timestamp of the most recent `calibrated`
   event in logs/routing-log.jsonl, or NONE. If routed traffic exists
   and more than 7 days have passed since that event (or since routed
   traffic began, when NONE), mark the line OVERDUE (D-0047). This is
   the external detector for the calibration loop itself — the one
   mechanism whose absence calibration cannot detect.
6. Working Tree at Boot = `git status --short` plus the unpushed
   commit count at session start. DIRTY or UNPUSHED means the
   previous session ended without the session-handoff check (D-0050):
   record it as a finding, do not silently absorb it into the new
   session's work.

Rationale for 1–2 (added 2026-07-03): a session that starts with a
silent series of file reads buries the report in tool noise; the
operator could not tell whether context recovery had happened.

7. Boot loads TWO layers (BOOT.md, D-0103 restructure 2026-08-18;
   HYBRID delivery 2026-08-25, D-0104): Layer A = orientation
   (README/PROJECT_CHARTER/ANTI_GOALS/PROJECT_PHILOSOPHY/
   ARCHITECTURE_BOOT); Layer B = state (CURRENT_CONTEXT).
   "Orientation Loaded (Layer A)" reports one of three values:
   `YES (injected)` — the hook's `--- BOOT LAYER A INJECTED ...` block
   was present and CLOSED by the `--- END BOOT LAYER A: ...` counted
   line, so Layer A reached context via the hook, not a session read;
   `YES (read)` — the session read the five files itself (hook
   absent/broken/truncated, or a pre-D-0104 deployment); `NO` —
   neither happened. "State Loaded (Layer B)" is unchanged: Layer B is
   never injected, always a session read. Rule 1's announcement duty
   covers the session's OWN reads (Layer B, and Layer A only in the
   `YES (read)` case).
   Current Phase / Current Objective are read from CURRENT_CONTEXT
   (Current Milestone / Current Task sections); ROADMAP.md remains the
   OWNER of phases/gates but is REFERENCE, point-read on demand, not
   boot-loaded — so the report sources the current-phase STATE from
   CURRENT_CONTEXT's milestone, not from a boot-load of ROADMAP. The
   decision log (DECISIONS.md) is likewise reference now, not a boot
   layer, so there is no "Decisions Loaded" line.

Rationale for 4 (added 2026-07-07, Architect correction): a session
began executing the next queued task immediately after its Boot
Report; the operator wants to review the recovered state and
explicitly greenlight the task first. Autonomy applies to executing
a confirmed task, not to choosing when to start one.
