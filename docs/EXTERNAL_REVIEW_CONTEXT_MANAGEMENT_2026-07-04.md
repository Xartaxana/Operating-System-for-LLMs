# External Review Report: Context Management and Supervision Architecture

Date: 2026-07-04

Status: external reviewer notes. This report records ideas and
recommendations only; it does not change project decisions by itself.
Any roadmap, architecture or decision change must still go through the
normal repository process.

## How the Reviewer Understands the Project

The project is not primarily another agent framework. It is an
operating layer for controlling LLM cost and reliability.

The core loop is:

1. Route all model traffic through one Gateway.
2. Enforce hard budgets deterministically through Guard.
3. Measure spend, latency, task categories and context repetition
   through Ledger.
4. Use Analyst and Shadow Evaluation to decide what can safely move
   from the Lead model to cheaper workers.
5. Treat every delegation decision as provisional until it is backed by
   measured evidence.

The important distinction is that routing, caching and compression are
not the contribution by themselves. Existing tools already cover much
of that surface. The project's niche is the decision loop: deciding
what is safe to route, cache or compress on this repository's traffic,
while proving that supervision itself costs less than the savings it
creates.

## High-Level Review

The strongest part of the project is the discipline around evidence:
Rule #1, Shadow Evaluation, judge calibration, retracted contaminated
runs, and explicit phase gates. This is more valuable than the current
amount of code.

The main risk is overstating evidence before production telemetry
exists. Rows marked `validated` from tiny synthetic samples can read
stronger than the data supports. A useful future distinction would be:

- `estimated`: expert prior, not measured;
- `provisionally_validated`: measured on synthetic or small samples;
- `production_validated`: measured on real traffic with sufficient
  volume and task-level cost;
- `rejected`: measured harmful under the stated conditions.

The second major risk is treating "context compression" as one lever.
In practice there are at least four different context-management levers,
with different safety and economics:

1. Prompt/cache layout: preserves semantics, reduces cost/latency.
2. Compaction/summarization: changes representation, risks semantic
   drift and loss of details.
3. Retrieval/memory: selects what to bring into context from an
   external store.
4. Context governance: controls who may write, delete, supersede or
   trust memory.

Phase 2 should therefore be framed as Context Management Evaluation,
not only Compression.

## Additional External Work Worth Considering

### Routing and Cascades

- AutoMix: routes to larger models using few-shot self-verification and
  a POMDP router; reports more than 50% cost reduction for comparable
  performance. This is worth considering before a fully trained router
  because it may need fewer preference pairs than RouteLLM.
  https://arxiv.org/abs/2310.12963
- Hybrid LLM: predicts query difficulty and routes between small and
  large models with a tunable cost/quality level; reports up to 40%
  fewer large-model calls with no quality drop.
  https://arxiv.org/abs/2404.14618
- HyDRA: a recent production-style capability router that predicts
  reasoning, code, debugging and tool-use requirements and matches
  them to model profiles. The useful idea is model-catalog decoupling:
  adding a model should be a config change, not retraining.
  https://arxiv.org/abs/2605.17106

Implication: keep RouteLLM in the Phase 2 queue, but compare it with
lighter confidence/self-verification baselines. A router evaluation
should have at least one simple baseline: "small first, escalate on
low confidence or failed judge".

### Provider Prompt and Context Caching

Provider-side caching should be evaluated before lossy compression.
It reduces cost without changing the model's effective prompt.

- OpenAI prompt caching works on exact prompt prefixes, exposes
  `cached_tokens`, supports `prompt_cache_key`, and recommends placing
  static content first and dynamic user content last.
  https://developers.openai.com/api/docs/guides/prompt-caching
- Anthropic prompt caching supports automatic caching, explicit
  breakpoints, TTL choices, and separate pricing for cache writes and
  cache hits. The important operational lesson is to put breakpoints on
  stable blocks, not on changing per-request content.
  https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- Gemini 2.5+ implicit caching is enabled by default and recommends
  large common contents at the beginning of the prompt, with similar
  prefixes sent close together.
  https://ai.google.dev/gemini-api/docs/caching

Implication: Ledger should distinguish raw input tokens from paid
uncached input tokens. The current "context repetition ratio" should
eventually split into:

- resent tokens;
- cached resent tokens;
- paid uncached resent tokens;
- effective input cost after cache discounts.

Without this, compression may be credited for savings that provider
prompt caching already delivered.

### LiteLLM and Semantic Response Caching

LiteLLM already supports response caching and semantic caching with
in-memory, disk, Redis, Qdrant, Redis semantic cache, Valkey semantic
cache, S3 and GCS backends.
https://docs.litellm.ai/docs/proxy/caching

Relevant papers:

- GPT Semantic Cache reports reduced API calls and lower latency by
  retrieving semantically similar previous answers.
  https://arxiv.org/abs/2411.05276
- SCALM studies semantic caching on real-world chat data and reports
  token-savings gains over GPTCache-style baselines.
  https://arxiv.org/abs/2406.00025
- ContextCache targets multi-turn conversations, where matching only
  the current query is unsafe because the same query can mean different
  things under different histories.
  https://arxiv.org/abs/2506.22791

Implication: semantic response caching is potentially useful for
formatting, extraction and repeated operational questions, but risky
for coding and reasoning. It should be validated by Shadow Evaluation
before it ever serves real responses. A cache hit should be treated as
another worker answer: cheap, but not trusted until validated.

### Context as a Tool

CAT ("Context as a Tool") argues that context management should not be a
passive fallback when the context window is full. Instead, context
maintenance becomes an explicit callable tool that the agent invokes at
milestones. CAT uses a structured workspace:

- stable task semantics;
- condensed long-term memory;
- high-fidelity short-term interactions.

https://arxiv.org/abs/2512.22087

Implication: the project's existing Context Manager idea can become a
runtime role. It should not merely select files at boot; it should
manage context during long tasks. A practical workspace for this
project could be:

- `stable`: BOOT, constitution, decisions and current objective;
- `working`: recent turns, current files and active diff;
- `evidence`: links to commits, database rows, evidence-log entries;
- `summary`: reviewed compaction of older work;
- `open_risks`: facts that must not be lost during compaction.

### Memory Addition and Deletion

Memory systems can harm agents when they grow without governance. One
study finds an "experience-following" behavior: agents retrieve similar
past experiences and then produce similar outputs, which can propagate
old errors or replay outdated solutions.
https://arxiv.org/abs/2505.16067

Implication: the project should not add every chat insight to memory.
Memory writes should be selective and reviewed. Memory needs deletion
or supersession rules, not only append rules.

Recommended memory states:

- `active`: current and authoritative;
- `superseded`: historically true, replaced by a later fact;
- `retracted`: known wrong or contaminated;
- `speculative`: useful idea, not yet accepted;
- `archived`: no longer operationally relevant.

### Agentic Context Engineering

ACE treats context as an evolving playbook curated through generation,
reflection and curation. Its main warning is context collapse: repeated
summarization can erase important details and produce a neat but
incorrect memory.
https://arxiv.org/abs/2510.04618

Implication: `CURRENT_CONTEXT.md` should stay concise and operational.
Long evidence histories should move to dedicated logs once they grow
large enough. A possible split:

- `CURRENT_CONTEXT.md`: only authoritative operational state;
- `EVIDENCE_LOG.md` or structured JSON: detailed run history;
- `LESSONS_LEARNED.md`: stable reviewed process lessons;
- `CURRENT_TASK.md`: exactly one current engineering task, if D-0025
  needs a stricter machine-readable surface.

### Context Engineering Taxonomy

A 2025 survey frames context engineering as retrieval/generation,
processing and management across RAG, memory systems, tool-integrated
reasoning and multi-agent systems.
https://arxiv.org/abs/2507.13334

A useful practical checklist for this project is:

- relevance: does this context help the current task?
- sufficiency: is enough included to solve the task?
- isolation: are real, synthetic, replay and judge contexts separated?
- economy: how many tokens and dollars does inclusion cost?
- provenance: what is the source of each fact?

### Temporal Graph Memory

Graphiti/Zep model memory as temporal context graphs with provenance,
validity windows, fact invalidation and hybrid retrieval.
https://github.com/getzep/graphiti
https://arxiv.org/abs/2501.13956

Mem0 is a simpler memory layer with add/search patterns over user or
agent memories.
https://github.com/mem0ai/mem0

Letta/MemGPT remains the relevant reference for stateful agents and
virtual context.
https://github.com/letta-ai/letta

Implication: do not add a graph database now. But copy the data model:
facts should have source, validity and supersession. This fits
DECISIONS.md, DELEGATION_TABLE.md, gate reports and judge calibration.

## Concrete Recommendations for This Project

### 1. Rename the Phase 2 workstream conceptually

Use "Context Management Evaluation" as the umbrella. Under it, compare:

1. Provider prompt caching.
2. Structured compaction.
3. Retrieval/memory.
4. Optional semantic response caching.

Compression is only one candidate, not the whole category.

### 2. Add cache-aware accounting before compression

Ledger should record provider cache fields where available:

- total prompt/input tokens;
- cached input tokens;
- cache write tokens;
- cache read tokens;
- output tokens;
- effective billed cost;
- cache hit ratio by model, category and session.

This is a prerequisite for deciding whether compression is actually the
right lever.

### 3. Introduce session and turn identity

The compression gate requires real sessions of at least five turns.
That needs durable fields:

- `session_id`;
- `turn_index`;
- `parent_request_id` or `trace_id`;
- `traffic_kind`;
- `context_strategy` (`raw`, `cached`, `compacted`, `retrieved`,
  `compressed`, etc.).

Without session identity, Phase 2 criteria will be hard to compute.

### 4. Evaluate provider caching first

Provider prompt caching is the lowest-risk cost lever because it should
not change the model's generated answer. It should be evaluated before
lossy token compression.

Acceptance idea:

- same task, same model, stable prompt prefix;
- measure cached tokens, latency and cost over repeated turns;
- verify response quality is unchanged by design;
- log effective savings after provider accounting.

### 5. Validate compaction through Shadow Evaluation

Every compaction method should be evaluated as:

```text
full context -> Lead answer
managed context -> same model answer
judge: are answers equivalent for the task?
ledger: did cost/latency improve enough?
```

This reuses the existing Shadow Evaluation philosophy.

### 6. Treat memory retrieval as a worker

A retrieval or memory system can be wrong by omission or by stale
inclusion. Its output should be logged and evaluated like any other
worker output.

Recommended metrics:

- retrieved token count;
- retrieval latency;
- provenance coverage;
- stale/superseded fact count;
- judge equivalence vs full context;
- downstream task success.

### 7. Add memory governance before memory scale

Before adding a vector store or graph memory, define rules for:

- what may be written;
- who reviews memory writes;
- how facts are superseded;
- how contaminated or wrong memory is retracted;
- how raw prompts are retained or redacted;
- how source provenance is preserved.

This matches the project's "Git is Memory" principle and prevents chat
history from silently becoming unreviewed memory.

### 8. Separate operational context from historical evidence

`CURRENT_CONTEXT.md` is already doing too much. It is still useful, but
it will eventually become expensive to boot and risky to summarize.

A future split should preserve boot reliability:

- keep `CURRENT_CONTEXT.md` short and authoritative;
- move long run histories to evidence logs;
- link evidence logs from `CURRENT_CONTEXT.md`;
- keep exactly one current task visible in the boot path.

### 9. Make context layout cache-friendly

For all gateway-mediated requests where the caller controls prompt
layout:

- put stable tool definitions, system instructions and project
  constitution first;
- put changing telemetry, timestamps and user-specific details last;
- avoid changing cacheable prefixes with timestamps or random IDs;
- preserve provider-specific cache fields in the request log.

### 10. Keep code context exact by default

Token-level compression is dangerous for code because small syntax or
identifier changes can break correctness. For code-heavy tasks, prefer:

- exact file snippets;
- symbol-aware retrieval;
- summaries around code, not inside code;
- judge-backed equivalence tests before any lossy code compression.

### 11. Add a context quality checklist to future specs

Every future context-management spec should answer:

- What context is included?
- What context is deliberately excluded?
- What is the provenance of each included fact?
- What is the token and cost impact?
- How is quality validated?
- How is stale or wrong context detected?
- What is the rollback plan?

### 12. Strengthen judge audit escalation rules

The current judge protocol is a good MVP guardrail: all status-changing
verdicts require chief-judge or Architect review, every reviewed pair
grows the calibration set, 1-2 random verdicts are audited per run, and
the judge is recalibrated after roughly five new calibration pairs.

However, 1-2 random audits should be understood as a heartbeat check,
not a statistical guarantee. If the true judge error rate were 10%, two
random checks would catch at least one error only about 19% of the time:

```text
1 - (1 - 0.10)^2 = 0.19
```

At a 20% error rate, two checks still catch at least one error only
about 36% of the time. That is useful as a smoke test, but it is not
enough to prove judge reliability for high-impact decisions.

Recommended audit policy:

- Keep 1-2 random audits as the minimum for small, low-impact runs.
- Increase audit size when the run is large, affects a Phase gate,
  introduces a new task category, uses a new source or target model,
  changes the judge prompt/model/version, or involves historically
  fragile categories such as coding, classification or borderline
  reasoning.
- If a random audit finds a judge error, freeze table updates from that
  run until expanded review completes.
- On any judge audit failure, immediately review at least five
  additional verdicts from the same run, or 20% of the run, whichever is
  larger. If the affected category is small, review the whole category.
- Classify the failure before changing prompts: judge error, ambiguous
  pair, missing rubric, contaminated sample, bad target answer, or task
  misclassification.
- Append all reviewed failures and borderline cases to
  `gateway/judge_calibration.json`.
- If the failure is a genuine judge error, recalibrate immediately
  instead of waiting for the normal "~5 new pairs" trigger.

Recommended severity ladder:

- One judge error in random audit: expanded audit plus immediate
  recalibration.
- Two judge errors in the same run or category: full manual review of
  that category before accepting status changes.
- A systematic pattern: freeze category status changes until prompt or
  model diagnosis is complete.
- Full calibration agreement below 90%: judge is not trusted for status
  changes until fixed, replaced or explicitly accepted by the Architect
  with a documented caveat.

Recommended immediate recalibration triggers:

- any random-audit mismatch where the chief judge labels the judge
  wrong;
- any mismatch on a status-changing verdict;
- judge model, provider, prompt, temperature or output schema changes;
- a new task category enters Shadow Evaluation;
- transition from synthetic to real traffic;
- any Phase 2 gate report;
- suspected contamination;
- provider-side model update under the same alias;
- sudden judge-cost or latency change suggesting the backend may have
  changed.

The principle is that random audits are the early-warning mechanism.
They should not merely record a failure; they should escalate the
amount of supervision until the judge is trustworthy again.

## Suggested Near-Term Task Queue

1. Review and sign off the already implemented Shadow Evaluation
   hardening (`traffic_kind` and proxy-accounted replay/judge costs).
2. Add session/turn identity to the request log.
3. Add cache-aware accounting fields to the Ledger.
4. Add a Phase 2 readiness section to `metrics.py` that includes cache
   fields once available.
5. Write a Context Management Evaluation spec before building
   compression.
6. Evaluate provider prompt caching before LLMLingua/PCToolkit.
7. Only then evaluate lossy compaction and retrieval/memory systems.

## Non-Goals Recommended by the Reviewer

- Do not add a graph database in Phase 1.
- Do not build a custom compression algorithm before evaluating
  provider caching and existing tools.
- Do not treat semantic cache hits as safe for coding or reasoning
  without Shadow Evaluation.
- Do not let raw chat history become project memory without review.
- Do not optimize for token reduction alone; optimize for effective
  billed cost at equal task quality.

## Bottom Line

The project should treat context as a managed resource with the same
discipline it already applies to model delegation. The next major
architectural move is not "compress context"; it is "measure and
validate context strategies." Provider caching, compaction, retrieval
and memory should all compete under Rule #1, using the same evidence
loop as Shadow Evaluation.
