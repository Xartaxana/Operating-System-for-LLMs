# Related Work

External projects, papers and articles overlapping with this project's
ideas. Surveyed 2026-07-03; context-compression section added
2026-07-04; evals section added 2026-07-08. Each entry states what we
can take from it.

## Evals / component-wise verification (validates D-0045..D-0049, feeds the eval plan)

### Тарасов, «Evals для чайников» (Habr, 2026)
https://habr.com/ru/articles/1042924/

Component-wise evals instead of end-to-end success rate: retrieval
precision, tool-call schema, state-consistency, retry/error
propagation, structured output, "I don't know" (unanswerable
questions must produce refusal, not hallucination), model swap.
Smoke-suite size 20–50 cases.

Take: per-tier golden sets for our agents — scout's recon eval with
known answers, including unanswerable and negative-claim cases, is
the direct application of the "I don't know" eval to F-14; run on
tier-model swap or agent-prompt edits.

### Тарасов, «Evals: что должен знать каждый AI-инженер в 2026» (Habr, 2026)
https://habr.com/ru/articles/1050736/

Eval stack: capability vs regression (regression suites hold ~100%),
online metrics, human golden sets, LLM-judge only as calibrated
first-pass (Bloom/Anthropic: judge-human Spearman 0.86 on 40
transcripts), execution-based evals as gold standard (verify results,
not words — SWE-bench Verified pattern). Statistical honesty:
confidence intervals, pass^k vs pass@k, never trust one run.
MCP-Atlas (1000 tasks, 220 tools): **63% of agent failures are
cognitive, not tool-call errors** — diagnostic breakdown beats a
single pass rate. CORE-Bench: a model jumped 42%→95% after fixing
grading bugs — fix the eval before blaming the model (our F-6
independently found the same failure mode in the judge). Comment
(daoxe): a routing eval layer — regression set of real requests,
periodic multi-model runs tracking latency/cost/errors — is exactly
our deferred Router loop (D-0029) described from the outside.

Take: (1) rejected-event notes classify the failure (spec / model
capability / recon / tooling) so calibration sees WHERE a tier
breaks, not just that it broke; (2) journal's accepted tasks are a
free regression set — replayable on the API contour via Shadow
Evaluation on model/price changes; (3) minimum-n and pass^k
discipline belongs in DELEGATION_TABLE Update Rules before statuses
move; (4) judge-human agreement should be a recorded number in
JUDGE_CALIBRATION_PROTOCOL, not a feeling. External confirmation:
"measure the system, not the model" is our D-0034 evidence-stream
design; "vibes don't scale" is D-0028.

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

## Context compression / memory management (Phase 2 candidates)

Surveyed 2026-07-04. The intra-session cost driver (stateless APIs
re-bill the whole message history every call) has a mature solution
landscape; per D-0030 we evaluate these before building anything.

### LLMLingua family (Microsoft, open source)
https://github.com/microsoft/LLMLingua

Token-level prompt compression: a small model drops tokens that do
not change the LLM's output (perplexity-guided), up to 20x compression.
LongLLMLingua adds question-aware coarse-to-fine compression for long
contexts (up to +21.4% quality with far fewer tokens,
arXiv:2310.06839); LLMLingua-2 reformulates compression as token
classification (task-agnostic, 2-5x at up to 2.9x lower latency).
PCToolkit (arXiv:2403.17411) bundles five methods (Selective Context,
LLMLingua, LongLLMLingua, SCRL, KiS) behind one interface.

Caveat from practitioners: perplexity-based compression can corrupt
code syntax — code-heavy contexts need specialized treatment.

Take: LLMLingua-2 / PCToolkit are the candidates to evaluate for
Phase 2 compression; never apply perplexity compression to code
context without validation.

### Letta (ex-MemGPT): architectural memory
https://www.letta.com/blog/agent-memory/

Positions itself literally as an "LLM Operating System": virtual
context with OS-style paging, recursive summarization of old
messages, agent-editable memory blocks, three-tier memory (core
in-context -> recall searchable -> archival vector store), background
"sleep-time" agents maintaining memory.

Take: the architectural answer to intra-session context growth;
overlaps our repository-as-memory idea at the inter-session level but
solves the intra-session level we deliberately deferred. If Phase 1
telemetry confirms the 50-62% prior, Letta-style recursive
summarization is the pattern to evaluate against LLMLingua-style
token compression.

### Why the problem is still open despite mature tools

Compression is lossy and task-dependent: nobody knows up front which
context fragment is the needle that cannot be dropped, so production
adoption is cautious and manual. This is exactly the gap our
machinery fills: **validating compression is the same problem as
validating delegation** — replay a request with compressed vs. full
context, let the calibrated judge rule equivalence, attach the
verdict as evidence. The Shadow Evaluation harness generalizes to
compression validation with no architectural change.

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
- MemGPT/Letta: virtual context management (memory paging) — see the
  dedicated "Context compression" section above.
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
5. Compression (Phase 2): evaluate LLMLingua-2/PCToolkit (token-level)
   and Letta-style recursive summarization (architectural) before
   building (D-0030); validate any of them with the existing Shadow
   Evaluation harness (compressed vs. full context, judge rules
   equivalence) — same loop as delegation validation.
