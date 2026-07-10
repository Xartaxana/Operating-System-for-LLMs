# Delegation Table

A living document. Every row starts as an estimate and is refined by
Shadow Evaluation during implementation (see ARCHITECTURE.md, D-0028).

Status values (four-state model, D-0035):

- `estimated` — expert prior, not yet measured;
- `provisionally_validated` — confirmed by Shadow Evaluation on
  synthetic or small samples (the label used to be `validated`;
  renamed 2026-07-07 so it cannot read stronger than the data);
- `production_validated` — confirmed on real traffic with sufficient
  volume and task-level cost; only this status may justify routing
  real traffic;
- `rejected` — delegation attempted and found harmful.

Cost = typical Lead token spend on this task type.
Value = how much frontier intelligence actually improves the result.

| Task type | Cost (Lead) | Value of Lead | Delegate to | Status |
|---|---|---|---|---|
| Strategic planning, architecture | High | Very high | Lead only | estimated |
| Research, hard debugging | High | Very high | Lead only | estimated |
| Idea generation | Medium | High | Lead, cheap model for expansion | estimated |
| Routine code generation | High | Medium | Middle | provisionally_validated |
| Summarization | Medium | Medium | Junior | provisionally_validated |
| Re-explaining known context | High | Low | eliminate via context management | estimated |
| Checking lists, verification passes | Medium | Low | Junior | estimated |
| Data extraction, JSON conversion | Medium | Low | Intern | provisionally_validated |
| Formatting (Markdown, tables) | Low–Medium | Low | Intern | provisionally_validated |
| Classification, tagging | Low | Low | Junior | rejected |
| Duplicate / repetition detection | Low | Medium | Ledger (no LLM) | estimated |
| Token and cost accounting | — | — | Guard/Ledger (no LLM) | estimated |
| Task decomposition + spec writing (coordinator role) | High | Very high | strongest available tier; judge-class candidate (D-0037) | estimated |
| Dispatch of an already-scoped task to a tier | Low | Low | deterministic rules / Router when its gate opens (D-0029) | estimated |

Claude Code workstream rows (D-0034; evidence stream = escalation
journal + acceptance verdicts, since replay is impossible on the
subscription contour):

| Task type | Cost (Lead) | Value of Lead | Delegate to | Status |
|---|---|---|---|---|
| Repo search, file reading, context gathering | Medium | Low | scout (Haiku subagent) | estimated |
| Implementation to a written spec, tests | High | Medium | builder (Sonnet subagent) | estimated |
| Code review, unclear-bug debugging | High | High | critic (Opus subagent) | estimated |
| Decomposition, spec writing, acceptance | High | Very high | Lead session only | estimated |

Flat delegation rule (D-0037): subagents never spawn subagents.
Parallelism = the Lead launches several subagents with independent
specs; a subagent that finds its task decomposable escalates back
("decomposable" is an escalation-journal category), it does not split
the task itself. On non-Claude contours the coordinator role may move
to a cheaper tier only via the decomposition row above gaining
evidence — never by default.

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

## Shadow Evaluation Log (relocated, D-0067)

The run log — one line per Shadow Evaluation run, with its accounting
and method caveats, retractions and chief-judge rulings — lives in
docs/SHADOW_EVALUATION_LOG.md (moved VERBATIM 2026-07-10, boot diet
round 2). NEW runs append there; a status change in the tables above
cites its evidence line in that file (Update Rule 1).
