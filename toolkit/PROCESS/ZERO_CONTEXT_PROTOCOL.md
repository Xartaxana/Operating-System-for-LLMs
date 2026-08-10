# Zero Context Recovery Protocol

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
