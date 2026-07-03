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
4. Shadow Evaluation compares TOTAL task cost (including retry loops),
   not per-request cost: external data shows a cheaper model can need
   10 loops where a frontier model needs 1, erasing the price advantage
   (see docs/RELATED_WORK.md, "Tokenomics in Action").

## External Evidence (priors, not measurements)

Figures from outside sources that our own telemetry should confirm or
refute. Sources and details: docs/RELATED_WORK.md.

| Claim | Figure | Source |
|---|---|---|
| Re-sent conversation history share of token spend | 50–62% | Unblocked, 2026 |
| Input tokens share of agentic session cost | ~85% (input:output ≈ 25:1) | Vantage, 2026 |
| Tokens wasted on redundant context / re-reading | 30–40% | arXiv:2604.22750 |
| Savings from summarization + budget-aware planning | 25–35% | arXiv:2604.22750 |
| Cascade routing cost reduction at equal quality | up to 98% (benchmarks) | FrugalGPT |
| GPT-4-class quality with 26% of frontier calls | 95% quality | RouteLLM |
| Prompt-cache discount on cached prefix | ~90% | provider pricing |
| Frontier vs cheap model retry loops on same task | 1 vs 10 loops | Klyshevich, 2026 |
