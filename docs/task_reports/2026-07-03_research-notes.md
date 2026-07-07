# Research Notes for Later Phases (2026-07-03)

Archived verbatim from CURRENT_CONTEXT.md on 2026-07-07 (D-0038).
The canonical homes of this content are docs/RELATED_WORK.md and
DELEGATION_TABLE.md ("External Evidence").

---

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.
- Phase 2 compression (surveyed 2026-07-04): evaluate LLMLingua-2 /
  PCToolkit (token-level) and Letta-style recursive summarization
  (architectural) before building; validate with the existing Shadow
  Evaluation harness (compressed vs. full context, judge equivalence).
  Never perplexity-compress code context without validation.
