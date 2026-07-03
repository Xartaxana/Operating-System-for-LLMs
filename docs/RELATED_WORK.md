# Related Work

External projects, papers and articles overlapping with this project's
ideas. Surveyed 2026-07-03. Each entry states what we can take from it.

## Routing / cascades (validates our Phase 2, D-0029)

### FrugalGPT (Stanford, 2023)
https://arxiv.org/abs/2305.05176

LLM cascade: query the cheapest model first, escalate on low confidence.
Matches best-single-model quality with **up to 98% cost reduction** on
benchmarks, or +4% accuracy at equal cost. Names three strategy families:
prompt adaptation, LLM approximation, LLM cascade.

Take: confidence-based escalation is the validated pattern for our Router;
our "delegate down, escalate up" hierarchy is the same idea inverted.

### RouteLLM (LMSYS / UC Berkeley, 2024)
https://github.com/lm-sys/routellm — open source, OpenAI-compatible server.

Routers trained on Chatbot Arena preference data. **95% of GPT-4
performance using 26% of GPT-4 calls** (matrix factorization router);
cost reductions of 85% (MT Bench), 45% (MMLU), 35% (GSM8K); >40% cheaper
than commercial routers at equal quality.

Take: per D-0030, evaluate RouteLLM as the Phase 2 Router implementation
before writing our own. Its routers need preference data — our Ledger +
Shadow Evaluation can produce exactly that.

## Cost telemetry / budget enforcement (overlaps Guard + Ledger)

### LiteLLM proxy (already our Gateway)
Built-in virtual keys, per-team/per-key budgets, rate limits.

Take: per D-0030, Guard should first try LiteLLM's native budget
mechanisms; custom code only for the 80%-warning semantics if missing.

### Langfuse / Helicone
Open-source observability layers (traces, cost attribution, evals).
Common production stack is LiteLLM (enforcement) + Langfuse (tracing);
LiteLLM ships a native Langfuse callback. Observability layers track
cost but cannot enforce budgets — enforcement belongs in the gateway,
which is exactly our Guard placement (D-0027 confirmed by ecosystem).

Take: if our SQLite Ledger ever stops sufficing, Langfuse is the
graduation path (already listed as deferred in ARCHITECTURE.md).

## Context repetition as the primary cost driver (validates Ledger metric)

Multiple independent sources confirm our primary suspicion:

- Vantage (2026): in agentic coding sessions input tokens are ~85% of
  session cost, input-to-output ratio ~25:1; the bill is driven by
  context accumulation, not per-token price.
  https://www.vantage.sh/blog/agentic-coding-costs
- Unblocked (2026): re-sent conversation history is **50–62% of total
  token spend** in Claude Code / Cline-style sessions.
  https://getunblocked.com/blog/why-ai-agents-burn-tokens/
- "How Do AI Agents Spend Your Money?" (arXiv:2604.22750): agents waste
  **30–40% of tokens** on redundant context and re-reading; proposed
  mitigations (observation summarization, budget-aware planning) could
  cut consumption 25–35% without hurting task success.
- Naive agent loops are quadratic: each step re-sends the whole history;
  a 20-step loop at 1K tokens/step bills ~210K cumulative input tokens.
- Prompt caching gives ~90% discount on the cached prefix but does not
  help the growing unique tail of the conversation.

Take: the Ledger's context-repetition ratio is measuring the right thing;
external numbers (50–62% re-sent, 30–40% waste) are the prior to beat.

## "Tokenomics in Action" (Klyshevich, LinkedIn, 2026)
https://www.linkedin.com/pulse/tokenomics-action-what-running-ai-dark-factory-costs-how-klyshevich-4t0xf/

Production numbers from autonomous coding agents ("dark factory"),
May 2026: 16.77B input tokens ($4,790), 15.91B cached ($455), 104.7M
output ($179) — input dominates exactly as our architecture assumes.
Five optimization levers with claimed savings: API response stripping
(40% of input tokens), prompt compression (10x on verbose prompts),
codebase indexing (50–60% of exploration tokens), model routing,
CI caching; combined claim ~80% cost reduction.

Notable counter-datapoint: cheaper models can cost MORE end-to-end —
identical task took GPT-mini-class 10 loops, mid-tier 3–5 loops,
frontier 1 loop. Delegation must be judged by total task cost,
not per-token price.

Take: (a) the loop-count effect goes into DELEGATION_TABLE.md update
rules as a required Shadow Evaluation metric; (b) input-token dominance
figures added as external evidence.

## LLM OS landscape (positioning)

- Karpathy's LLM OS sketch: LLM as CPU, context window as RAM, tools as
  syscalls — conceptual framing, no cost supervision.
- AIOS (arXiv:2403.16971): OS-style scheduling/resource management for
  agents; academic kernel, not cost-driven.
- MemGPT: virtual context management (memory paging) — relevant later
  for context compression, orthogonal to supervision.
- Curated list: https://github.com/bilalonur/awesome-llm-os

Take: no project in this space combines deterministic budget enforcement
+ spend analytics + data-validated delegation as its core loop. That
combination (Guard/Ledger/Analyst + Shadow Evaluation) is our niche;
routing itself is commoditized (RouteLLM), so our contribution is the
supervision economics, not the router.

## Implications recorded

1. Router (Phase 2): evaluate RouteLLM before building (D-0030).
2. Guard (Phase 1 step 2): try LiteLLM native budgets first (D-0030).
3. Shadow Evaluation must measure total task cost including retry loops,
   not per-request cost (loop-count effect).
4. Context-repetition ratio has external priors: 50–62% re-sent history,
   30–40% redundant tokens; our Ledger should confirm or refute locally.
