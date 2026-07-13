# External Reviewer Report — Supervised Delegation / OS for LLMs

Date: 2026-07-13
Reviewer stance: third-party architecture and product reviewer
Scope: repository architecture, gateway, tools, toolkit packaging, routing policy, validation loops, budget/accounting logic.

Constraint: review only. No project files were changed except this report.

## Verification Performed

- Read core docs: `README.md`, `ARCHITECTURE.md`, `DELEGATION_TABLE.md`, `ROADMAP.md`, `CURRENT_CONTEXT.md`, `PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md`.
- Read gateway code: `gateway/guard.py`, `gateway/sqlite_logger.py`, `gateway/metrics.py`, `gateway/shadow_eval.py`, `gateway/analyst.py`, `gateway/regression_runner.py`, `gateway/config.yaml`, `gateway/budgets.yaml`.
- Read subscription-contour telemetry and enforcement tools: `tools/usage_report.py`, `tools/savings_report.py`, `tools/journal_validator.py`, `tools/mechanism_gate.py`.
- Read toolkit packaging docs and representative copies under `toolkit/`.
- Checked active git hooks: `.githooks/pre-commit`, `.githooks/commit-msg`, `core.hooksPath`.
- Ran test suites:
  - `python -m pytest tools gateway -q` -> 372 passed.
  - `python -m pytest toolkit -q` -> 322 passed.

## Executive Summary

The project has a strong central idea and unusually good self-discipline: deterministic checks are separated from AI judgment, delegation evidence is logged, and many prior defects have been converted into tests or calibration checks. The core thesis is coherent: the Lead should spend attention only on decomposition, acceptance, policy, and hard judgment, while lower tiers and deterministic tools handle everything else.

The main risks are not ordinary test failures. The main risks are economic and operational:

1. The system can make wrong routing decisions if status vocabulary, toolkit copies, prices, or category mappings drift.
2. The budget guard is reactive to already-logged spend and can under-enforce the current request.
3. The subscription contour depends heavily on discipline plus weekly calibration, so Lead self-exemption is not caught early enough.
4. The public toolkit can lag behind the dogfooding repo while still passing its own tests.
5. The API-key contour is a good lab/gateway, but not yet a complete agentic product for users with API keys.

## High-Priority Findings

### 1. Budget and quota guard can overshoot on the current request

Relevant files:
- `gateway/guard.py`
- `gateway/budgets.yaml`

The guard checks prior spend/tokens before the call. It does not reserve estimated cost or tokens for the request being admitted. A large request, a high `max_tokens`, or concurrent requests can pass the pre-call check and only be reflected after completion.

Why it matters:
- A paid API request can cross the budget wall before the next request is blocked.
- Free-tier token windows can still get provider 429s if multiple aliases or parallel calls consume the same physical quota.
- The system's promise is deterministic budget enforcement; reactive accounting is weaker than that.

Suggested fixes:
- Add preflight admission math using prompt token estimate + `max_tokens` / configured cap.
- Reserve budget/quota in SQLite before the call, then reconcile after completion.
- Use a transaction or lock for check-and-reserve.
- Add provider-key quota groups, not only per-alias windows.
- Make the failure mode loud: "current request cannot be proven under quota" should fail closed for exam/calibration traffic.

### 2. Shadow Evaluation still emits legacy `validated`

Relevant file:
- `gateway/shadow_eval.py`

The project documentation uses a four-state table:
- `estimated`
- `provisionally_validated`
- `production_validated`
- `rejected`

But `shadow_eval.py` still computes and writes `validated` in its status path. This is a semantic regression risk: the code can write a status that no longer means what the table means.

Why it matters:
- `production_validated` is the only status that should justify routing real traffic.
- `provisionally_validated` is explicitly weaker.
- A legacy `validated` string collapses that distinction.

Suggested fixes:
- Replace legacy `validated` with `provisionally_validated` for Shadow Evaluation output.
- Make status values an enum shared by table update code and metrics.
- Add a test that no writer can introduce a status outside the four-state vocabulary.
- Consider refusing `--update-table` unless the evidence line contains sample count, distinct prompt count, judge model, judge calibration state, errors, truncation, and cost basis.

### 3. Public `toolkit/` has known drift from root implementation

Relevant files:
- `toolkit/gateway/metrics.py`
- `toolkit/gateway/shadow_eval.py`
- `toolkit/gateway/sqlite_logger.py`
- `CURRENT_CONTEXT.md` toolkit port queue

The toolkit suite passes, but the toolkit code is not equivalent to the current root code. Examples observed:
- `toolkit/gateway/metrics.py` still contains an R2 readiness stub that says real categorized traffic is currently unavailable.
- `toolkit/gateway/shadow_eval.py` lacks the newer max-token/truncation handling and stored-category preference.
- `toolkit/gateway/sqlite_logger.py` lacks newer schema columns such as cache-token/category support.

Why it matters:
- The toolkit is the public adoption surface.
- Users can get outdated economic logic while tests still pass.
- This directly threatens the project's goal: saving money by routing correctly.

Suggested fixes:
- Add a release gate comparing root and toolkit core files by hash or semantic version.
- Maintain a manifest of intentionally divergent files with reasons.
- Add tests that assert toolkit contains the same critical fixes as root, or explicitly marks them as not applicable.
- Do not publish a toolkit snapshot while root has queued economic/accounting fixes not ported.

### 4. Lead self-exemption is audited too late

Relevant files:
- `CLAUDE.md`
- `PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md`
- `logs/routing-log.jsonl`
- `tools/usage_report.py`

The policy requires `dispatch_skipped` whenever the Lead keeps a delegable task. This is good, but enforcement is mostly by discipline and weekly calibration. If the Lead silently performs scouting, routine edits, extraction, or formatting, the system may only notice later.

Why it matters:
- The central product promise is that the top level will not hoard cheap work.
- Weekly discovery is too slow for expensive sessions.
- Silent self-exemption biases the evidence base: the table sees delegated tasks, not tasks the Lead wrongly kept.

Suggested fixes:
- Add a cheap daily/opportunistic detector:
  - top-level session did many file reads/searches without scout delegation or skip event;
  - commit has large routine diff without builder/critic evidence;
  - prompt/session contains extraction/formatting/summarization patterns without delegation;
  - high Lead-token session has zero delegated or dispatch_skipped events.
- Report candidates, not final violations. AI/Lead can judge semantics.
- Put the detector into Boot Report or SessionStart as a short warning when stale.

### 5. API-key contour is not yet a complete agentic deployment

Relevant file:
- `ARCHITECTURE.md`

The architecture correctly states that the gateway is currently a lab role and lacks:
- API-side coordinator,
- tool harness for workers,
- repository access for recon,
- journal writer.

Why it matters:
- A user with API keys from multiple providers wants a working delegation product, not only a proxy and evaluation lab.
- The gateway can measure model calls, but does not yet provide the full loop: decompose -> dispatch with tools -> accept/reject -> journal -> calibrate.

Suggested fixes:
- Define a minimal API-contour coordinator interface.
- Pick one tool harness path for workers and validate it on a real repo task.
- Implement journal writes for API-worker runs using the same event vocabulary.
- Run the same acceptance/witness discipline as subscription contour.
- Keep the first version narrow: scout/read-only recon and builder-to-spec before general autonomy.

### 6. Raw prompt and response logging is a privacy and adoption risk

Relevant files:
- `gateway/sqlite_logger.py`
- `gateway/README.md`
- `toolkit/gateway/sqlite_logger.py`

The gateway stores raw `prompt` and `response` text in SQLite. The README documents this honestly, and the reason is valid: repetition metrics need prompt content. But external users may run this on private or commercial repositories.

Why it matters:
- The project stores secrets, source snippets, customer data, or proprietary context if the model sees them.
- A local SQLite DB is easy to copy, commit by accident, or retain indefinitely.
- This can block adoption in real projects.

Suggested fixes:
- Add `GATEWAY_LOG_RAW_TEXT=false` mode.
- Store hashes/minhashes or prefix fingerprints for repetition metrics when raw logging is disabled.
- Add configurable retention TTL and purge command.
- Add redaction hooks for API keys, bearer tokens, `.env`, private URLs, and obvious credentials.
- Add a startup warning showing where `requests.db` lives and whether raw text logging is enabled.

## Medium-Priority Findings

### 7. Category/status mapping is duplicated

Relevant files:
- `DELEGATION_TABLE.md`
- `gateway/metrics.py`
- `gateway/shadow_eval.py`

`VALIDATED_DELEGABLE_CATEGORIES` mirrors the delegation table manually. The weekly protocol checks drift, but the runtime still depends on duplicated knowledge.

Suggested fixes:
- Move delegation rows to a machine-readable source, for example `delegation_table.yaml`.
- Generate markdown table from that source.
- Let metrics import the machine-readable statuses instead of maintaining a frozenset.

### 8. Price registry is hardcoded and fragile

Relevant files:
- `tools/usage_report.py`
- `tools/savings_report.py`
- `gateway/config.yaml`

The code is careful to avoid silent zero cost for unknown models. That is good. But prices are still hardcoded and must be manually updated as providers change model names and pricing.

Suggested fixes:
- Centralize prices into a versioned registry with effective date and source note.
- Add a "pricing stale" check for known providers.
- Store actual provider/model and alias in every row, then price by provider_model where possible.
- Make unknown price a calibration blocker when it affects economic conclusions.

### 9. Quotas are alias-based, but providers meter keys/accounts

Relevant files:
- `gateway/budgets.yaml`
- `gateway/config.yaml`
- `gateway/guard.py`

Multiple aliases can share one provider key. Current quota windows are per alias, which is not enough for provider free-tier limits shared by a key/model/account.

Suggested fixes:
- Add `quota_group` or `provider_key_group` in config.
- Check both alias quota and group quota.
- Preflight quota should sum all aliases in the group.

### 10. Runtime config is not validated strongly enough

Relevant files:
- `gateway/config.yaml`
- `gateway/budgets.yaml`
- `toolkit/delegation.config.yaml`

The system assumes alias names, roles, budgets, quotas, judge bindings, and delegation config stay consistent. Several checks exist in prose or calibration, but not as a startup validator.

Suggested fixes:
- Add `gateway/config_check.py`.
- Validate:
  - every role binding has a budget or explicit "unlimited";
  - every paid alias has a cost source;
  - judge is not judging its own underlying model unless explicitly allowed;
  - quota aliases map to provider groups;
  - toolkit-generated config matches `delegation.config.yaml`.

### 11. Judge quality is handled seriously, but should be tied to status updates

Relevant files:
- `gateway/shadow_eval.py`
- `PROCESS/JUDGE_CALIBRATION_PROTOCOL.md`

The project calibrates judges and records failures. Good. But table updates should mechanically require current calibration metadata.

Suggested fixes:
- `--update-table` should require `--judge-model` and a recent successful calibration unless the run is explicitly marked heuristic-only/no-status-change.
- Evidence lines should include calibration id/date/score.
- Status movement should be impossible from difflib-only evidence except to "estimated" or a clearly weak provisional bucket.

### 12. Onboarding is promising but still too manual for API-key users

Relevant files:
- `toolkit/.claude/skills/onboarding/SKILL.md`
- `toolkit/delegation.config.yaml`
- `toolkit/gateway/config.template.yaml`

Onboarding gives a good ordered process, including exams and warnings. For API-key users, the system should do more deterministic validation.

Suggested fixes:
- Probe each configured model with a tiny request.
- Verify the model name, provider key env var, and basic pricing.
- Write a capability matrix: supports tools, max context, max output, streaming, structured output, known quota.
- Refuse to mark onboarding complete while `api` fields are blank under `api-keys` or `both`.

## Product Development Ideas

### Delegation opportunity report

Produce a short daily or session-level report:
- tasks delegated,
- tasks skipped with reason,
- suspected missed delegations,
- Lead-token share,
- cost per accepted delegated unit,
- false accept rate by tier,
- retries by tier.

This would make "Lead hoarding" visible much earlier than weekly calibration.

### Economic routing margin

Do not route merely because a lower tier is cheaper per token. Require:

`expected_savings >= coordination_cost + judge_cost + retry_cost + variance_margin`

For unstable categories, use a conservative multiplier until enough production evidence exists.

### Retry-loop accounting

Update Rule 4 is correct: total task cost matters, not one-shot cost. The code should model this directly:
- group attempts by task/category;
- count rejected retries;
- compare accepted-unit cost by tier;
- move statuses down if cheap tier wins one-shot but loses after retries.

### Confidence and sample quality

Shadow Evaluation should track:
- distinct prompt count,
- duplicate prompt ratio,
- truncation count,
- unjudged count,
- judge disagreement,
- source answer quality issues,
- pass rate confidence interval.

This prevents small or contaminated samples from looking stronger than they are.

### Public toolkit release discipline

Add a release checklist:
- root core and toolkit core sync status,
- migration status,
- smoke install into empty repo,
- smoke install into existing repo,
- onboarding completed,
- first delegated cycle accepted,
- raw logging warning shown,
- config validation passed.

### Privacy modes

Offer three modes:
- Full telemetry: raw prompt/response stored.
- Safe telemetry: no raw text, only token/cost/latency/category and fingerprints.
- Minimal telemetry: cost and quota only.

The default for public toolkit should probably be Safe telemetry, with Full telemetry explicitly opted in.

### API-contour worker harness

A practical order:
1. Read-only scout worker with repo search/read tools.
2. Builder worker limited to owned paths and a written spec.
3. Witness wrapper that runs tests and writes output.
4. Journal writer.
5. Acceptance loop.
6. Only then consider an automatic router.

This keeps the API contour aligned with the project's own rule: evaluate existing tools first, build infrastructure only after the gate opens.

## What Looks Strong

- The architecture's split between deterministic enforcement and AI judgment is sound.
- The routing journal has meaningful typed fields and an active pre-commit validator.
- The commit-message mechanism gate is active via `core.hooksPath`.
- The project avoids silent zero-cost accounting for unknown Claude Code models.
- Judge calibration is treated as a first-class dependency rather than assumed.
- Tests are broad and currently green.
- The project records failures and converts many of them into mechanisms or calibration checks.

## Bottom Line

The project is directionally strong and already more rigorous than most multi-agent routing experiments. The next improvements should not be more policy prose. They should be small, boring mechanisms that protect the economic claims:

1. Close the current-request budget overshoot.
2. Remove legacy status vocabulary.
3. Prevent root/toolkit drift before release.
4. Detect missed delegation earlier than weekly calibration.
5. Make API-key mode a real agentic contour, not just a lab gateway.
6. Add privacy-safe telemetry modes for external adoption.

