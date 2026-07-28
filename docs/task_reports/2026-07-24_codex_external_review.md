# External Review: policy-as-code, delegation, economy

Date: 2026-07-24
Reviewer: Codex, сторонний технический ревью
Scope: repository read-only review; no code or policy changes made.

## Executive summary

Проект уже зрелый как исследовательский полигон: ключевые правила
делегирования не только записаны в `CLAUDE.md`, но частично стоят на
execution path через hooks, pre-commit/commit-msg gates, журнал,
DoD/witness checks, routing log validation, budget guard, ledger and
weekly calibration.

Главный риск не в отсутствии политики, а в неровной границе между:

- инвариантами, которые реально fail-closed держит код;
- инвариантами, которые пока держатся предупреждением;
- инвариантами, которые ловятся только недельной калибровкой;
- инвариантами, которые вообще требуют человеческого/Lead-суждения.

Для проекта с лозунгом "вся политика и все правила должны охраняться
кодом" это нормальная текущая стадия, но следующая фаза должна
сфокусироваться на экономически критичных leak paths: перерасход
budget/quota одним большим запросом, самоисполнение Lead вместо
делегирования, техническая возможность scout писать, и ручная
синхронизация delegation economics между Markdown и Python.

## What is strong already

1. Политика загружена в контекст и формализована.
   `CLAUDE.md` содержит явные routing rules, Role != tier, журнал,
   DoD/manifest, leaf routing, degradation handling and command
   hygiene. Это закрывает исходный failure mode "модель сама не
   делегирует".

2. Часть правил стоит на execution path.
   `.claude/settings.json` подключает `SessionStart`, `PreToolUse`,
   `PostToolUse`, `SubagentStop`, `Stop`; среди них
   `dispatch_gate.py`, `hygiene_gate.py`, `dod_gate.py`,
   `main_gate.py`, `journal_echo.py`, `critic_snapshot.py`.

3. Журнал маршрутизации хорошо типизирован.
   `tools/journal_validator.py` проверяет append-only, typed fields,
   witness for builder acceptance, worker_ref, task lifecycle,
   D-0058 acceptance matrix, judge basis category, timestamps and
   task_id novelty.

4. Роль builder уже технически ограничена flat delegation.
   `.claude/agents/builder.md` не имеет `Task/Agent` в tools, что
   превращает "не запускай других агентов" из дисциплины в
   конфигурационный инвариант.

5. Есть измерительная культура.
   `gateway/metrics.py`, `shadow_eval.py`, `usage_report.py`,
   `savings_report.py`, `calibration_counts.py`, weekly calibration
   protocol and findings registry делают проект проверяемым, а не
   декларативным.

6. Тестовая база сильная.
   Раздельный прогон дал:
   - `python -m pytest tools/ -q`: 1357 passed, 34 warnings.
   - `python -m pytest gateway/ -q`: 191 passed.
   Полный `python -m pytest tools/ gateway/ -q` не уложился в 120s,
   но раздельные прогоны зелёные.

## Priority findings

### P0. Budget Guard blocks only after previous spend, not projected spend

Files:

- `gateway/guard.py`, `check_budget`
- `gateway/guard.py`, `check_quota_windows`
- `gateway/guard.py`, `Guard.async_pre_call_hook`

Current behavior:

- pre-call guard checks already logged spend;
- dollar wall blocks when `spent >= budget`;
- token wall blocks when `spent >= limit`.

Problem:

One large request can cross the budget or rolling token quota because
the current request is not reserved or projected before the call.

Why it matters:

This is central to the product promise. A cost-saving system must not
only report overspend; it should prevent predictable overspend,
especially on paid aliases and provider free-tier ceilings.

Recommendation:

Add projected-spend enforcement:

- estimate current request prompt tokens before call;
- include requested/allowed max output tokens;
- enforce `spent + projected >= limit` for hard walls;
- optionally allow a configurable safety margin per alias/provider;
- log refused projected requests separately from post-fact budget
  blocks.

For high-cost aliases, fail closed when projection is unavailable.
For cheap/local aliases, a warning may be enough.

### P0. Scout is declared read-only but technically has Bash

File:

- `.claude/agents/scout.md`

Current behavior:

Scout says it is read-only, but tools include `Bash`.

Problem:

`Bash` can write through shell redirection, PowerShell equivalents,
scripts, generated files, or side effects. The current `hygiene_gate`
blocks journal shell writes, not every possible project write.

Why it matters:

Recon is supposed to be the cheapest and safest tier. If scout can
write, "read-only" is a prompt norm, not an enforced property.

Recommendation:

Prefer removing `Bash` from scout and relying on `Read`, `Glob`,
`Grep`. If shell search is still needed, introduce a restricted
read-only command wrapper or a specific allowed command surface.

### P1. Silent self-execution by Lead is still mostly post-factum

Files:

- `CLAUDE.md`, R1/R2/R8
- `tools/dispatch_gate.py`
- `tools/main_gate.py`
- `PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md`, checks 1/2/8

Current behavior:

`dispatch_gate.py` checks shape before a downward dispatch. It cannot
see when the coordinator simply performs scout/builder-class work
itself without a dispatch or `dispatch_skipped` event.

Problem:

This is the highest-value economic leak: the expensive coordinator can
still keep delegable work because no dispatch event exists to validate.
Weekly calibration can detect patterns, but the spend has already
happened.

Recommendation:

Introduce a cheap "work-intent / route-intent" layer:

- before substantial work, coordinator records intended work items:
  `scout`, `builder`, `critic`, `lead`;
- `main_gate` compares observed reads/edits/test runs against either
  `delegated` or `dispatch_skipped`;
- multiple small builder-class edits may be grouped as one
  `"батч мелочей"` intent;
- the gate should warn first, then block only after clear recurrence.

This would mechanize the "top must not keep everything to itself"
principle without needing an LLM classifier on every move.

### P1. `main_gate` can allow completion without green verification

File:

- `tools/main_gate.py`

Current behavior:

`CONSECUTIVE_BLOCK_LIMIT = 2`; after two consecutive blocks,
`main_gate` records `skipped_after_2_blocks` and returns exit 0.

Problem:

The safety valve prevents infinite blocking, but it also creates a
known route to end a session without a green run after code edits.

Why it matters:

For policy-as-code, a break-glass path should not look like success.

Recommendation:

Keep the anti-deadlock behavior, but change its semantic result:

- completion may proceed only as `blocked/unsafe`, not as acceptable
  work;
- require an explicit journal event or acceptance basis above the
  session tier before the work can be accepted;
- make `skipped_after_2_blocks` a hard acceptance blocker in the
  next layer, not merely a telemetry fact.

### P1. Raw prompt/response logging defaults to enabled in HQ

File:

- `gateway/sqlite_logger.py`

Current behavior:

`GATEWAY_LOG_RAW_TEXT` defaults to true in HQ. Prompt and response
text are stored unless explicitly disabled.

Problem:

This is understandable for a research deployment because Shadow
Evaluation and context-repetition metrics need raw prompts. For a
product used with users' API keys, it is a privacy and compliance risk.

Recommendation:

Split telemetry modes explicitly:

- `accounting-only`: no raw prompt/response, no replay;
- `redacted`: PII/secrets redaction before storage;
- `full-replay`: raw storage, explicit opt-in, retention clock;
- `synthetic-only`: shadow evaluation only on sanitized regression
  sets.

Add retention policy and purge tooling. Raw prompt logging should be a
visible deployment decision, not an incidental environment variable.

### P1. Delegation economics are duplicated between Markdown and code

Files:

- `DELEGATION_TABLE.md`
- `gateway/metrics.py`

Current behavior:

`VALIDATED_DELEGABLE_CATEGORIES` in Python manually mirrors rows in
`DELEGATION_TABLE.md` whose statuses are provisionally/production
validated.

Problem:

Weekly calibration can detect drift, but the runtime economics still
depend on manual synchronization.

Recommendation:

Make the delegation table structured data:

- `delegation_table.yaml` or `delegation_table.json` as source of
  truth;
- generated Markdown for humans;
- runtime imports structured categories/statuses directly;
- status moves happen through a small audited command that requires
  evidence pointers.

This is a direct policy-as-code improvement.

### P1. `basis="judge"` is validated by category, not by proven leaf graph

File:

- `tools/journal_validator.py`

Current behavior:

The validator allows `basis="judge"` when `category` is one of the
leaf categories, currently recon/implementation.

Problem:

The field `category` is self-declared on the event. A graph/integration
task can be made to look leaf-like if the event category is wrong.

Recommendation:

Add typed leaf artifacts:

- `leaf_id`;
- pinned intent keys;
- performer tier;
- judge verdict id;
- deterministic retry/escalation state.

Then `accepted(basis="judge")` should link to that artifact. The
validator can verify the link structurally, while the higher tier still
judges semantic correctness.

### P2. Hook payload/schema drift often fails open

Files:

- `tools/dispatch_gate.py`
- `tools/hygiene_gate.py`
- `tools/dod_track.py`
- `tools/critic_snapshot.py`
- `tools/session_context.py`

Current behavior:

Many hooks intentionally fail open on malformed/foreign payloads to
avoid breaking the harness.

Problem:

This is operationally sensible, but if the harness changes payload
shape, a hook may silently stop enforcing until weekly calibration or
a live incident catches it.

Recommendation:

Add a lightweight live liveness probe for each blocking hook:

- invalid builder dispatch must be blocked;
- valid builder dispatch must pass;
- journal shell write must be denied;
- DoD/main gate must block a known dirty track;
- validator must reject a synthetic invalid staged journal line.

This should run in install/upgrade and weekly calibration.

### P2. Toolkit wiring checker is awkward when run from the source repo

File:

- `toolkit/tools/wiring_check.py`

Observed behavior:

Running `python toolkit\tools\wiring_check.py --check` from the staff
repo reports a hooksPath mismatch because it treats `toolkit/` as the
host root and expects `toolkit/.githooks`.

Problem:

For a product/toolkit, the distinction between "checking the toolkit
source" and "checking an installed host" must be explicit.

Recommendation:

Add CLI parameters:

- `--host-root`;
- `--kit-root`;
- `--mode source|installed`;
- clear output when the command is run against the wrong root.

## Product and architecture improvements

### 1. Make routing decisions first-class data

Current journal events are useful, but routing intent is often inferred
from what happened. Add a route-plan object for non-trivial tasks:

- task graph or leaf flag;
- intended tier per node;
- expected acceptance route;
- cost ceiling;
- batching boundary;
- reason for any planned skip.

The journal then records execution against the plan. This makes "Lead
kept work for itself" easier to detect.

### 2. Track cost per accepted task as the main dashboard

Expose a dashboard/report with:

- accepted task count by category/tier;
- gross cost;
- judge cost;
- retry/escalation cost;
- Lead coordination cost;
- cost per accepted task;
- late defect rate;
- false accept rate;
- percentage of work delegated down;
- token cost of context switching.

The current project has most raw ingredients, but the product metric
should be front and center.

### 3. Add batch economics

The project correctly notices that frequent model switches consume
tokens. Add explicit batch accounting:

- batch id;
- number of small edits/recon questions grouped;
- saved coordinator turns;
- extra worker setup/context cost;
- net savings.

Then batching can be promoted from policy text to measured routing
strategy.

### 4. Add provider/key capability registry

For API-key deployments, maintain structured provider capability data:

- model id;
- provider;
- key env var;
- price source and date verified;
- context window;
- max output;
- tool support;
- structured output support;
- streaming support;
- quota model;
- rate limits;
- supports cache accounting;
- last calibration result per role.

Unknown price/capability should make economic conclusions
`not_computable_yet`, never silently assumed.

### 5. Enforce quota pools by provider key, not only alias

Several aliases can share the same provider key and underlying quota.
Alias-level quota can under-enforce global provider ceilings. Add
provider/key pools:

- `quota_pool: groq_free_key_1`;
- aliases draw from the same pool;
- Guard checks alias wall and pool wall.

### 6. Build install/upgrade as an audited transaction

The findings around Dog/AO3 show that shipping mechanisms by copy or
delta can miss invariants. Treat installation and upgrade as a
transaction:

- preflight checks;
- target root detection;
- full target content for executable enforcement files;
- liveness probes;
- rollback on failed probe;
- adoption ledger update;
- revision stamp.

### 7. Make role files part of the upgrade contract

Role files are policy carriers. They should be diffed, versioned and
examined during upgrade, not treated as static installation artifacts.

### 8. Replace read-modify-write session state where facts matter

`dod_track` style JSON state is vulnerable to lost updates under
parallel hooks. For facts that feed blocking gates, prefer:

- append-only JSONL;
- SQLite;
- file lock;
- or atomic per-event files merged by readers.

### 9. Add acceptance package artifacts

For each accepted worker task, persist one small package:

- spec;
- given/owns/non-goals;
- worker_ref;
- changed paths;
- witness;
- critic verdict if any;
- judge verdict if any;
- cost summary;
- acceptance basis.

This would reduce reliance on final chat messages and make later
audits cheaper.

### 10. Separate "research HQ" from "product default"

HQ can keep richer logs, raw prompts, experimental aliases and manual
calibration. A user-facing toolkit should default to:

- privacy-first logging;
- fewer moving parts;
- explicit provider configuration;
- fail-closed only where the user understands the cost;
- clear "what protection is active" status output.

## Suggested execution order

1. Fix Guard projected-spend/quota enforcement.
2. Make scout technically read-only.
3. Add route-intent or work-plan ledger to catch Lead self-execution.
4. Convert delegation table to structured source of truth.
5. Add hook liveness probes for install/upgrade/calibration.
6. Add provider/key quota pools and capability registry.
7. Formalize acceptance package artifacts.
8. Split telemetry/privacy modes for product deployments.

## Verification performed during review

Commands run:

- `python -m pytest tools/ gateway/ -q`
  - timed out after 120 seconds with no failure output.
- `python -m pytest tools/ -q`
  - `1357 passed, 34 warnings in 103.65s`.
- `python -m pytest gateway/ -q`
  - `191 passed in 43.60s`.
- `git status --short`
  - clean before writing this report.

No code or existing policy files were changed as part of the review.
