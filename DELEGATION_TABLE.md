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
| Routine code generation | High | Medium | Middle | rejected |
| Summarization | Medium | Medium | Junior | validated |
| Re-explaining known context | High | Low | eliminate via context compression | estimated |
| Checking lists, verification passes | Medium | Low | Junior | estimated |
| Data extraction, JSON conversion | Medium | Low | Intern | validated |
| Formatting (Markdown, tables) | Low–Medium | Low | Intern | validated |
| Classification, tagging | Low | Low | Junior | rejected |
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

## Shadow Evaluation Log

Evidence for Update Rule 1. One line per Shadow Evaluation run.

Caveat on the comparison method (2026-07-03): sim is difflib
character-level similarity. High-sim `validated` verdicts are
trustworthy; low-sim `rejected` verdicts are SUSPECT — a verbose
answer scores near zero against a terse one even when semantically
identical (classification sim=0.04 is likely this artifact). Rejected
rows must be re-checked once the LLM judge replaces the heuristic
(see CURRENT_CONTEXT.md, Current Task).

- 2026-07-03  category=coding  source=lead-gemini target=intern  n=2  sim=0.10  cost_source=$0.0044 cost_target=$0.0000  -> rejected
- 2026-07-03  category=summarization  source=lead-gemini target=intern  n=2  sim=0.52  cost_source=$0.0016 cost_target=$0.0000  -> validated
- 2026-07-03  category=extraction  source=lead-gemini target=intern  n=2  sim=0.91  cost_source=$0.0003 cost_target=$0.0000  -> validated
- 2026-07-03  category=classification  source=lead-gemini target=intern  n=2  sim=0.04  cost_source=$0.0021 cost_target=$0.0000  -> rejected
- 2026-07-03  category=formatting  source=lead-gemini target=intern  n=2  sim=0.60  cost_source=$0.0004 cost_target=$0.0000  -> validated
