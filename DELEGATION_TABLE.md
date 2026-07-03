# Delegation Table

A living document. Every row starts as an estimate and is refined by
Shadow Evaluation during implementation (see ARCHITECTURE.md, D-0028).

Status values:

- `estimated` — expert guess, not yet measured;
- `validated` — confirmed by Shadow Evaluation on real requests;
- `rejected` — delegation attempted and found harmful.

Cost = typical Lead token spend on this task type.
Value = how much frontier intelligence actually improves the result.

| Task type | Cost (Lead) | Value of Lead | Delegate to | Status |
|---|---|---|---|---|
| Strategic planning, architecture | High | Very high | Lead only | estimated |
| Research, hard debugging | High | Very high | Lead only | estimated |
| Idea generation | Medium | High | Lead, cheap model for expansion | estimated |
| Routine code generation | High | Medium | Middle | estimated |
| Summarization | Medium | Medium | Junior | estimated |
| Re-explaining known context | High | Low | eliminate via context compression | estimated |
| Checking lists, verification passes | Medium | Low | Junior | estimated |
| Data extraction, JSON conversion | Medium | Low | Intern | estimated |
| Formatting (Markdown, tables) | Low–Medium | Low | Intern | estimated |
| Classification, tagging | Low | Low | Junior | estimated |
| Duplicate / repetition detection | Low | Medium | Ledger (no LLM) | estimated |
| Token and cost accounting | — | — | Guard/Ledger (no LLM) | estimated |

## Update Rules

1. A row may change status only with evidence attached
   (Shadow Evaluation sample or production incident).
2. New task types are added as they appear in the Ledger.
3. "Re-explaining known context" is tracked as the primary suspected
   cost driver; its row is retired when context compression ships.
