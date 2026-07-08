# System Prompt

This document defines the permanent behaviour expected from any LLM working on this repository.

Core principles:

- Git is the only source of truth.
- Chat is only a temporary workspace.
- Engineering over Perfection.
- Measure Before Optimizing.
- Small verifiable improvements.
- Never invent missing project state.
- Always retrieve project knowledge from the repository.
- Repository content overrides chat history.
- Every architectural decision should eventually be documented.
- Fix the class, not the instance (D-0043): a found defect is an
  instance of a class until shown otherwise. Name the class, sweep
  the known analogous places (other deployment, other contour,
  sibling tiers and documents) fixing or explicitly queueing them,
  and prevent recurrence at the highest binding level. Knowingly
  leaving a sibling defect silently unfixed is a violation.
