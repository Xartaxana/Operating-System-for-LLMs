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

## Agent orchestration with evidence gates (validates D-0037/D-0046, feeds the acceptance plan)

### pi-autopilot (Salikhodjaev, npm/GitHub, 2026)
https://github.com/ismailsaleekh/pi-autopilot

Extension for the Pi coding agent: dependency-cleared child-agent
orchestration. v0.6.1 published 2026-07-08, single author — young,
not battle-tested; surveyed same day at operator's request. Parent
session decomposes work into unit specs with roles
(strategy/implement/validate/fix/bughunt) — flat orchestration like
our D-0037; blocker-escalation ≈ our `decomposable`. No cost-tier
routing at all — adjacent problem (execution evidence + isolation),
which is why its mechanisms transfer without competing with our
table. Three mechanisms we lack:

1. **Witness coverage.** Execution audits reject
   declared-but-unwitnessed commands, fake-green tests,
   self-certification; work sits in audit-review states until
   evidence is clean and an INDEPENDENT validation unit confirms.
   Take: builder acceptance requires attached run artifacts
   (witness), symmetric to our D-0046 trail rule — adoption plan
   stage 1 (F-17).
2. **context_budget as an enforced tool**, not discipline: the
   parent cannot read project files before the budget gate reports
   ok (85% threshold). Take: a PreToolUse hook is our analog IF
   calibration checks 10/11 show the discipline actually leaks —
   plan stage 3, data-gated (Rule #1: don't build before evidence).
3. **Path claims.** WRITE on owned_paths / READ on read_only_paths
   per unit; "WRITE scope never expands silently — a child needing
   new edit authority must emit a blocker". Take: parallel builder
   specs declare owned paths, Lead checks intersection before
   launch — plan stage 2, at first parallel dispatch. Per-unit git
   worktrees NOT taken (Rule #1: harness worktree isolation already
   exists; no volume to justify our own).

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

## Agent tool harnesses for gateway workers (survey 2026-07-09, D-0030)

Question: an existing tool-loop that lets gateway-bound models (Groq
builder, local scout) read/grep/patch a repository through OpenAI-style
function calling, pointed at OUR proxy so accounting stays in
requests.db. Operator-named candidates + survey additions; WebFetch
digests are small-model output — verify specifics at adoption time.

- **Pi (pi.dev, github.com/earendil-works/pi)** — the RECOMMENDED
  candidate. MIT, TypeScript, 69k stars, v0.80.3 (June 2026), active.
  Confirmed on the load-bearing criterion: custom providers via
  `registerProvider(..., {baseUrl, api: "openai-completions"})` or
  `~/.pi/agent/models.json`, with a native Ollama example
  (docs/custom-provider) — our gateway is a drop-in endpoint, local
  models included. Scriptable dispatch (print/JSON, RPC, SDK modes) fits
  a coordinator calling it per task. Extensible tools via SDK.
  Weakness: NO built-in permission system — a read-only scout profile
  means supplying a restricted tool set via the SDK/extension (or
  containerizing), not flipping a flag. Ecosystem kinship: pi-autopilot
  (whose author's external review shaped D-0053/F-18) builds on it.
- **GSD Pi (github.com/open-gsd/gsd-pi; operator-named as gsd-2, since
  moved)** — NOT a harness: a standalone local-first coding agent plus
  meta-prompting / spec-driven methodology (MIT, v1.9.0, 849 stars; can
  wrap Claude Code/Cursor as providers). Its process layer overlaps
  what OUR policy already owns (specs, routing, acceptance) — adopting
  it would duplicate the coordinator role, not equip workers. Custom
  base_url CONFIRMED by the deep-dive (see «GSD Pi deep-dive» below);
  mechanism-extraction plan in CURRENT_CONTEXT queue.
- **vibe-engineer (github.com/ismailsaleekh/vibe-engineer)** — v0.1,
  4 stars, provider integration undocumented; agent-native TS workflow
  harness (skills/memory/verification) rather than a model-agnostic
  tool-loop. Not a candidate now; revisit if it matures.
- **Aider (aider.chat)** — survey addition from priors: Python,
  git-aware repo edits, repo-map, native OPENAI_API_BASE override —
  the classic builder-harness over an OpenAI-compatible endpoint.
  Not operator-named; verify current state at adoption.

Take: prototype path = Pi + registerProvider(gateway): a scout profile
(read/grep-only tool set via SDK) bound to the local model with the
D-0057 golden set as its entrance exam, and a builder profile bound to
builder-groq. Measured context (2026-07-09 fresh import): the scout
tier's all-time accounted spend is $1.33 (141 turns) — the economic
case for a local scout is ~zero; the case that stands is RESILIENCE
(subscription outage/limit fallback, D-0039-adjacent) plus the
API-contour second pilot needing recon at all (Deployment targets,
ARCHITECTURE.md).

## GSD Pi deep-dive (survey 2026-07-09, operator-ordered)

Full-project reading of open-gsd/gsd-pi (ex gsd-build/gsd-2; MIT,
v1.9.0 of 2026-07-08, built on the Pi SDK; docs at lets-gsd.com).
NOT to be confused with fulgidus/pi-gsd — an unrelated unofficial
port of glittercowboy/get-shit-done to Pi. Sources: repo README,
lets-gsd.com landing + docs (v2 auto-mode/configuration/providers,
v1 architecture), releases v1.1.0–v1.9.0. WebFetch digests are
small-model output (standing caveat) — verify specifics at adoption.

Identity check on the load-bearing claim: custom OpenAI-compatible
endpoint IS supported — `~/.gsd/agent/models.json` with
`baseUrl`/`apiKey`/`api: "openai-completions"`, local providers
Ollama/LM Studio/vLLM/SGLang. Cross-confirmed independently: GSD Pi
runs on the Pi SDK, and this is the exact models.json mechanism our
live Pi prototype already uses against the gateway (t-011+). Closes
the «custom base_url unconfirmed» note above.

Mechanism inventory, mapped to our system (their name → ours):

1. **Per-phase model profiles with fallbacks** (`models:` per
   research/planning/execution/execution_simple/completion/subagent,
   each with `fallbacks:` list) → our DELEGATION_TABLE tiers; the
   fallback chain is D-0039 degradation, automated at config level.
2. **Budget enforcement**: `budget_ceiling` USD +
   `budget_enforcement: warn|pause|halt`; per-unit token/cost capture
   broken down by phase/slice/model; `per_unit_cost_cap_usd`
   (v1.6.0) → our Guard (Phase 1 step 2) and Ledger concepts —
   implemented and shipping in a same-space project. Prior art for
   D-0030 «try LiteLLM native budgets first», not a refutation of it.
3. **Stuck-loop detection**: sliding-window pattern analysis over
   dispatch history (catches A→B→A→B, not just repeats),
   same-unit consecutive-dispatch caps (2–3), one retry with a deep
   diagnostic prompt then STOP for human → our Rule 6 (2 rejected →
   escalate) enforced mechanically instead of by discipline.
   **Zero-tool-call guard** (v1.3.0: «zero-tool-call rate-limit guard
   distinguishes transient provider errors from genuine loops») →
   deterministic detector for exactly our F-14 fabrication class
   (t-011/t-016: 0 tool calls + confident fabricated answers).
4. **Pre-dispatch preflight blocks**: dirty-file-overlap detection,
   unmerged-conflict check, worktree validation; STATE.md writes
   guarded by O_EXCL lockfile with 10s stale-lock detection → our
   D-0060/F-23 parallel-sessions class, automated.
5. **Verification machinery**: `verification_commands` (e.g. lint,
   test) run post-execution with `verification_auto_fix` and
   `verification_max_retries: 2`; artifact-presence verification
   redispatches with failure context (cap 3); an assessment artifact
   «only counts as completed when it contains a canonical verdict
   field» → our witness/DoD (D-0052/D-0054), machine-checked.
6. **Context hygiene**: fresh context per unit; `UnitContextManifest`
   names the tool policies and files injected at dispatch; token
   profiles (budget mode inlines minimal context, quality mode
   everything); observation masking (`observation_mask_turns: 8`,
   `tool_result_max_chars: 800`); `gsd_exec` caps noisy stdout/stderr
   into `.gsd/exec/` files → directly relevant to our «Pi default
   prompt weight vs free-tier ceilings» class (PI_HARNESS break #3,
   t-015 TPD abort).
7. **Crash recovery**: SQLite-backed unit/worker state; on death the
   next run synthesizes a recovery briefing from persisted tool
   calls; headless auto-restart with backoff; soft/idle/hard timeouts
   (20/10/30 min) → their in-run analog of our session handoff; tied
   to their auto-mode state machine, not portable piecemeal.
8. **Planning-layer gates**: package legitimacy audit tags
   `[SLOP]/[SUS]/[ASSUMED]` in RESEARCH.md (supply-chain);
   decision-coverage gates (decisions must map to shipped artifacts,
   one BLOCKING); codebase drift gate (last_mapped_commit..HEAD vs
   STRUCTURE.md, auto-remap on threshold) → cousins of our
   SIBLING_MAP axis-enumeration (rule 10b) and snapshot drift.

WXP («XML preprocessing engine», v2.0 marketing): appears in search
results only; nowhere in the official docs read — not confirmed, not
carried further.

Take (prior verdict STANDS, sharpened): GSD Pi is our closest
same-space neighbor — a code-enforced version of much of our policy
layer, single-project, workflow-driven. What it does NOT have is our
core loop: cost-crossover-driven tier assignment validated by spend
data (Shadow Evaluation / weekly calibration against cc_usage).
Adopting the agent would replace the Lead coordinator and forfeit
that loop; extracting mechanisms keeps it. Extraction plan (what:
zero-tool-call guard, gateway fallback chains, dispatch context
manifest, Rule-6 deterministic check, witness auto-collection; when:
per item) lives in the CURRENT_CONTEXT queue, entry «GSD Pi adoption
plan».

## OpenClaw survey (2026-07-10, запрос оператора; t-022 + второй проход Lead — первое применение D-0066)

https://github.com/openclaw/openclaw — «personal AI assistant» поверх
20+ мессенджер-каналов. TypeScript monorepo, v2026.6.11, очень
активный; Gateway = локальный control plane (sessions/channels/tools),
multi-agent = привязка каналов к агентам, НЕ ярусная маршрутизация
задач. Подтверждённые негативы (t-022, сверено grep'ом Lead): нет
tier-routing по цене/способности, нет журнала делегирований с
приёмкой, нет аналога weekly-калибровки — ядро нашей ниши не занято
и здесь (согласуется с «LLM OS landscape» выше).

След второго прохода (Lead читал сам, полный клон в scratchpad):
docs/concepts/{delegate-architecture,model-failover,usage-tracking,
parallel-specialist-lanes,context}.md целиком,
docs/automation/cron-jobs.md (1–120), grep bootstrap-бюджетов по
agent-loop/context/agent-workspace, сверка negative-хитов в src/.
Итог второго прохода: delegate-architecture — пусто для нас
(организационная identity, не ярусы); model-failover и context —
несущие и в дайджесте отсутствовали/были поверхностны. Состав плана
после второго прохода ИЗМЕНИЛСЯ — F-26 воспроизведён на месте.

Механизмы, взятые в план (как и когда — очередь в CURRENT_CONTEXT):

1. **Boot-бюджет per-file** (`/context list`: на каждый инжектируемый
   файл «raw vs injected» + флаг TRUNCATED + warning-блок в промпт;
   пер-файловый кап `bootstrapMaxChars` 20k + общий 60k chars).
   Наш аналог: порог 100KB меряется одним числом на handoff (D-0050);
   per-file разбивка делает виновника роста видимым сразу. КАК:
   строка per-file в чек 4 session-handoff (следующее касание скилла)
   + per-file вывод в B3 SessionStart hook при его постройке (уже в
   очереди, gated первой калибровкой). Отдельной работы НЕ открывать.
2. **Provider-reported квоты, не самоподсчёт** (usage-tracking: «no
   estimated billing», тянуть usage/quota endpoint провайдера;
   нормализация «X% left»). Наши quota-стены t-018 ведут скользящие
   окна сами; Groq отдаёт фактический остаток в rate-limit-заголовках
   ответа. КАК: сверка счётчиков стен с заголовками — data-gated
   (Rule #1): строится только если калибровка/прогоны t-015 покажут
   дрейф стен (ложный отказ или пропуск реального лимита).
3. **Lane contract** (parallel-specialist-lanes: письменный контракт
   лейна — Owns / Does-not-own / Chat budget / Handoff rule / Tool
   posture; параллелизм как дефицитный ресурс, caps maxConcurrent).
   КАК: поля Owns/Non-goals/Handoff влить в шаблон A3 dispatch
   context manifest при его постройке (A3 уже в очереди). Не раньше.

Prior art / валидация — записано, работ не открывается:

- **Strict selection**: явный выбор модели пользователем НИКОГДА не
  фолбэчится молча — «reports the failure instead of answering from
  an unrelated fallback». Внешняя валидация нашего t-018-решения «no
  cross-model fallback для экзаменационного трафика, стены отказывают
  громко».
- **Двухступенчатый failover** (model-failover.md): ротация
  auth-профилей ВНУТРИ провайдера (счётчик
  `rateLimitedProfileRotations`, дефолт 1) до перехода к следующей
  модели; лестница cooldown'ов 30с/1м/5м с 24h-окном сброса;
  раздельные lane'ы billing-disable vs transient rate-limit;
  model-scoped cooldown (сосед по провайдеру ещё доступен); probe
  первичной модели раз в 5 мин + sticky fallback + уведомление только
  на смене состояния; структурные `fallbackStep*` поля в логах.
  Готовый дизайн на случай второго ключа Groq/Gemini и словарь для
  наших failure_class/quota-стен. Не строим: фолбэк-цепочки уже
  сознательно отклонены (A2, t-018).
- **Cron в gateway-процессе** (cron-jobs.md): персистентные job'ы в
  SQLite с историей прогонов, `--model` на job (job primary с
  конфигурируемыми fallbacks), event-триггеры (скрипт возвращает
  `{fire, state}`, состояние персистится, 30s/5 tool-calls бюджет),
  watchdog'и фаз запуска, reconciliation потерянных прогонов. Prior
  art для штатного режима «оператор координирует с Sonnet, Fable
  батчем на очередь Lead-задач» — если оператор захочет его
  механизировать, дизайн брать отсюда.
- **utilityModel per-function** (models.md:45): отдельная дешёвая
  модель на короткие внутренние задачи. Это наша функция→модель
  (D-0062) в миниатюре — валидация словаря, дубля не строим.

NOT adopted (чтобы не ре-литигировать): каналы/мессенджеры и
companion-приложения (не наш скоуп), delegate identity/sandboxing
(харнесс + permission-гигиена уже покрывают), compaction/session
pruning/context engine и memory-системы (внутрисессионный контекст
владеет Claude Code; наш слой — межсессионный, repo-as-memory),
usage-footer шаблоны (UI-поверхность).

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
