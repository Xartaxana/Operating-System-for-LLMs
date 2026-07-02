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

### Layer 2 — Decisions

Architectural knowledge.

Includes:
- DECISIONS.md
- ADR/*

### Layer 3 — Operational State

Current status of the project.

Includes:
- ROADMAP.md
- CURRENT_CONTEXT.md (future)

### Layer 4 — Repository History

Complete Git history.

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
