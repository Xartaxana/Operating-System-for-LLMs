# Memory Architecture

## Purpose

The project treats memory as a first-class subsystem.

The objective is to make project continuity independent from any particular LLM or chat history.

---

## Principle 1 — Git is the source of truth

Git is the only long-term memory.

Chat conversations are temporary workspaces.

No important project knowledge should exist only inside a conversation.

---

## Principle 2 — Layered Memory

### Layer 1 — Constitution

Always loaded.

Includes:
- PROJECT_CHARTER.md
- PROJECT_PHILOSOPHY.md
- ANTI_GOALS.md
- SYSTEM_PROMPT.md
- CLAUDE.md (auto-loaded by the Claude Code harness itself at session
  start — routing policy; D-0041: delegation is opt-in, the policy
  must precede any task, so it cannot wait for an on-request boot)

### Layer 2 — Decisions and Process

Architectural knowledge and engineering protocols.

Includes:
- DECISIONS.md
- docs/adr/*
- PROCESS/*

### Layer 3 — Operational State

Current status of the project. Loaded at boot; kept small by the
D-0038 archiving rule (closed work moves to docs/task_reports/).

Includes:
- ROADMAP.md
- CURRENT_CONTEXT.md
- DELEGATION_TABLE.md

### Layer 4 — Repository History and Archive

Complete Git history, docs/task_reports/, deep documents
(WHITE_PAPER.md, docs/).

Never fully injected into an LLM context.

Retrieved on demand.

---

## Principle 3 — Context Manager

LLMs should not remember project rules.

A Context Manager prepares the appropriate context from Git before every reasoning session.

---

## Principle 4 — Constitution is Mandatory

The Constitution layer is always included in the reasoning context.

This prevents architectural drift.

---

## Principle 5 — Full Repository Access

The operating system must always have access to the complete repository.

Only the loaded context is selective.

Storage is complete.
