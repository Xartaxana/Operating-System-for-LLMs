# Zero Context Recovery Protocol

Привязка: D-0022, D-0024 (ретро-свип rule-10 2026-07-11).

## Goal

Verify that a completely new LLM session can continue the project using only the repository.

## Input

- Git repository
- BOOT.md
- No chat history

## Success Criteria

The new session correctly identifies:

- project mission
- current phase
- engineering principles
- active roadmap
- current task
- repository structure

without relying on previous conversation history.

## Rule

If the test fails, improve the repository rather than the prompt or the model.
