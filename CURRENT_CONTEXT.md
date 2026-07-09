# Current Context

## Maintenance Rule (D-0038)

This file holds LIVE state only: the current milestone, the single
authoritative task (D-0025), the queue, condensed system state,
strategic guidance still steering decisions, and operational
environment notes. When a task or workstream CLOSES (review ACCEPTED
or Architect sign-off), the session that closes it moves the spec,
execution report and review VERBATIM to docs/task_reports/ and leaves
a one-line pointer here. Evidence is never deleted, only relocated.
Rationale: this file is loaded on every boot (BOOT.md); boot context
is a paid resource — the project's own subject.

## Current Milestone

Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034), on top
of a complete Phase 1 MVP. Plan of record:
docs/UNIFIED_PLAN_2026-07-07.md (D-0034..D-0036).

## Current Task (Authoritative, D-0025)

t-013 CLOSED 2026-07-09 (builder+critic+Lead): the groq streaming
tool-call break did NOT reproduce on identical litellm 1.90.2
(critic verified install date - no upgrade confound); t-012
observation reclassified as likely Groq-side transient. Artifact:
gateway/tools_stream_check.py (persistent isolator); PI_HARNESS
breaks rewritten - #1 closed, #3 = NEW class "Pi default prompt
weight (~8.9k tok) vs Groq free-tier ceilings" (TPM 8000 blocks
builder-groq; TPD 100k/day aborted the t-015 exam).
RE-EXAMS (tail of the same operator-confirmed queue item):
- t-016 qwen3:4b on hardened profile: FAIL 0/7 CONFIRMED, both
  traps, fabricated Trail, thinking trace shows explicit
  simulation-mode decision. Local scout CLOSED until a stronger
  local candidate fits 6GB VRAM (re-exam debt cleared).
- t-015 llama-70B re-exam: attempt 1 aborted by Groq TPD quota
  (rejected/tooling, NOT a model verdict); RETRY after quota reset
  ~21:05 local 2026-07-09 - the one open item of this task. Recipe
  for the retry session: hardened profile text + Pi call form =
  gateway/PI_HARNESS.md; the 7 questions verbatim =
  PROCESS/SCOUT_GOLDEN_SET.md (key liveness re-verified 2026-07-09,
  t-015 delegated notes); start the proxy per PI_HARNESS "Прокси
  перед запуском" (session-local proxy/scratchpad do not survive);
  journal the retry as t-015 attempt 2 (continuation).
Coordinator work done meanwhile: t-014 scout (AO3 R14 anchors)
accepted; calibration check 15 landed (commit 47b185c).

Previous: Task 3 (Phase 2 readiness digest) ACCEPTED 2026-07-09 and archived:
docs/task_reports/task-3_phase2-readiness.md (task_id t-002; builder
+ critic ПРИНЯТЬ + Lead witness 108/108). Digest first output: G1
met (15 days, consecutiveness not yet verified — follow-up queued),
C2 met (32 sessions), R1 not met (4/30 pairs), rest honestly not
computable / manual check.

Eval stage 1 items 2+3 DONE 2026-07-09 (D-0057): scout golden set
(PROCESS/SCOUT_GOLDEN_SET.md, baseline run t-006 = 7/7 PASS incl.
both mandatory trap questions) + regression rule for agent-prompt
edits (calibration check 14). Same day also closed: G1
consecutive-streak follow-up (t-004, met now requires >=14
CONSECUTIVE days) and traffic_kind default drift (intentional —
Tasks 1-2 finding 4; pointer comment added at the migration site).
Operator-raised same day (screenshot of an AO3 Sonnet session
self-certifying builder-class acceptances): sessions assume the
Lead ROLE from the policy's addressee -> F-22 + D-0058 (role !=
tier; capability matrix per actual session model; acceptance only
from above; critic-skip concession only above the worker; the
planned "coordinate from Sonnet, batch Fable" mode legalized as
the normal regime). Landed in both deploys; detector = calibration
check 6 (amended). Later same day: a PARALLEL session committed
D-0059 (task-pipeline gate, c2e2d98) while this one worked — the
resulting task_id collision (t-008 x2) became F-23 + D-0060
(parallel-session discipline; eval-plan Stage 2 landed by its real
trigger). First calibration should also tier-check the D-0059
commit's session per D-0058 (check 5/6). NEXT task awaits operator
pick.

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (operator in-chat:
  "текста политики CLAUDE.md — одобрено"): CLAUDE.md routing rules
  as of commit 171078c (rules 1-11, Роль != ярус, degradation,
  journal vocabulary, command hygiene). Later policy changes follow
  the normal mechanism discipline; this acceptance closed the last
  open item of Phase 1.5 step 2.
- Evidence so far (2026-07-09, after t-004..t-006): builder n=4
  accepted, critic n=3 accepted, scout n=4 accepted (D-0046 cycles
  with spot-checks); 1 rejected (t-001 attempt 1,
  failure_class=capability), 0 escalations. ALL statuses estimated
  (Update Rule 1).
- Retro baseline AO3 (cc_usage, pre-routing): $276.70 accounted +
  $57.82 sidechain self-correction (Task 6). Weekly loop compares
  cost per accepted unit + escalation rate, NOT frontier share alone
  (Architect correction — see baseline section below).
- Next: accumulate >=1 week of routed traffic, then the FIRST weekly
  calibration (PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md, 12 checks;
  run ends with a `calibrated` journal event; staleness watched by
  the Boot Report's Last Calibration line, D-0047).
- 2026-07-08 day narrative (interim 18h read, Task 7 closure,
  dead-tier revival, F-1/D-0041/D-0042, first degradation cycle,
  mechanism day F-12..F-16 / D-0044..D-0051): archived —
  docs/task_reports/2026-07-08_routing-dogfooding-day.md.

## System State (condensed, 2026-07-08)

- Phase 0 closed 2026-07-03 (Zero Context Recovery Test passed).
- Phase 1 steps 1-4 built and verified: Gateway (LiteLLM + SQLite
  request log), Guard (daily per-model budgets, warn 80% / refuse
  100%), Ledger (metrics.py digest), Analyst (Qwen3-4B via Ollama
  through the gateway under its own alias).
- Shadow Evaluation (step 5) operational: shadow_eval.py with
  --judge-model, --calibrate, --categories, honest Rule #1 cost
  extraction (proxy-accounted costs; never a silent $0); sampler
  excludes judge/replay traffic. Remaining: traffic volume, paid-Lead
  baseline (needs ANTHROPIC_API_KEY).
- Judge: judge-groq (groq/openai/gpt-oss-120b, free tier), calibrated
  13/13 at temperature=0, reproduced twice. Protocol:
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (D-0031) — status-changing
  verdicts need chief-judge review; 1-2 random audits per run. No
  local judge on this hardware (Qwen3-4B 11/13, below the 90% bar);
  fallback order: judge-groq > paid API judge > local 4B restricted.
- traffic_kind tagging live: real/synthetic/replay/judge; gate G1
  counts only 'real'. The tag travels via extra_body metadata —
  litellm's metadata= kwarg does NOT reach the wire (verified; see
  comments in sqlite_logger.py / shadow_eval.py).
- Tests: gateway 49/49, tools 31/31 green. gateway/conftest.py
  isolates every test (tmp DB + full litellm callback-list
  snapshot/restore — restoring litellm.callbacks alone is NOT
  enough, litellm copies the logger into six lists at call time).
- requests.db: 199 rows (judge 149, synthetic 50, real 0 — the API
  contour has carried no real traffic yet); cc_usage table alongside
  (11149+ turns of which 1759+ sidechain, idempotent import, both
  transcript layouts, agent_id/agent_type attribution + haiku
  pricing, 0 NULL-cost rows).
- DELEGATION_TABLE.md: 4-state model (D-0035).
  provisionally_validated: coding -> Middle, summarization /
  extraction / formatting -> intern; rejected: classification ->
  intern. Claude Code workstream rows: estimated.
- Delegated Tasks 1, 2, 3, 4, 5, 6, 7: ACCEPTED and archived
  (docs/task_reports/ — see Archive below).

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- $1,177.48 accounted all-time (8747 turns, 79 sessions, 4 projects).
  Per model: sonnet-4-6 $735 / opus-4-8 $206 / fable-5 $198 /
  sonnet-5 $39.
- CACHE READS DOMINATE: 97.6% of input-side tokens are cache reads;
  accounted savings vs uncached $7,117 on a $1,178 total — first
  hard evidence for the D-0036 ordering (measure net-of-cache before
  building any compression).
- G1 LOOKS GREEN RETROACTIVELY: real traffic 20 consecutive days
  (>=14 required). Formal check = Task 3 digest + written gate
  report + Architect signature (D-0033). G2 (judge 13/13) holds.
- SPEND MIX — ARCHITECT CORRECTION (2026-07-07): the baseline is
  CENSORED data (operator rationed frontier usage), so it cannot
  refute "the smartest model burns most". Correct reading — frontier
  burns FASTEST per unit: opus $0.264/turn, fable $0.216 vs sonnet
  $0.063-0.114 (2-4x). Consequences: (a) success metric is cost per
  accepted unit by tier + escalation rate, NOT frontier share;
  (b) the escalation journal measures the true tier boundary; the
  weekly loop watches the recent-window trend, not all-time totals.

## Remaining Lead-tier Queue

- D-0043 sweep remainder: add the "report sibling defects" line to
  the nine AO3 QA-pipeline agent prompts on their next touch.
- Local scout evaluation (operator-approved 2026-07-09; D-0062
  function→model rebinding, NOT a build): (1) pull the scout tier's
  accounted spend from cc_usage (per-agent attribution, Task 7);
  (2) survey existing tool harnesses for GATEWAY WORKERS generally
  (broadened 2026-07-09, operator direction): one harness serves
  both the Groq builder (read/grep + patches via OpenAI-style
  function calling, which Groq supports) and the local scout —
  D-0030: evaluate before building any tool-loop. Operator-named
  candidates to include (2026-07-09): Pi-agent (https://pi.dev —
  same ecosystem as pi-autopilot, whose author's review shaped
  D-0053/F-18; priors in RELATED_WORK), vibe-engineer
  (https://github.com/ismailsaleekh/vibe-engineer), gsd-2
  (https://github.com/gsd-build/gsd-2); plus whatever the survey
  itself surfaces. STEPS 1-2 DONE 2026-07-09 (operator-ordered run):
  (1) scout spend measured — $1.33 all-time / 141 turns (fresh
  cc_usage import): economic case ~zero, the standing case is
  RESILIENCE + the API-contour second pilot needing recon at all
  (Deployment targets); (2) survey recorded in RELATED_WORK «Agent
  tool harnesses»: Pi (earendil-works) RECOMMENDED — MIT, 69k stars,
  custom provider with baseUrl/openai-completions (gateway drop-in,
  native Ollama example), scriptable JSON/RPC/SDK; caveat: no
  built-in permissions, read-only scout profile = restricted tool
  set via SDK. GSD Pi (ex gsd-2) = standalone agent+methodology,
  overlaps our policy layer, not a harness; vibe-engineer immature
  (v0.1); aider noted from priors. STEP 3 DONE 2026-07-09
  (operator-ordered): Pi prototype LIVE — npm
  @earendil-works/pi-coding-agent 0.80.3, provider os-gateway in
  ~/.pi/agent/models.json (intern + builder-groq through our
  proxy, accounting lands in requests.db). ENTRANCE EXAM (t-011):
  qwen3:4b FAILED 0/7 — zero tool calls, all answers fabricated
  incl. both mandatory traps and a fabricated "verified" claim
  (Runs log in PROCESS/SCOUT_GOLDEN_SET.md); (4) row "recon ->
  local intern" does NOT enter the table. Infrastructure
  separately VALIDATED: Pi -> gateway -> ollama_chat structured
  tool calling works (setup lessons: Pi -p needs closed stdin;
  models.json cost requires cacheRead/cacheWrite; litellm ollama/
  prefix drops tools — intern moved to ollama_chat/ in
  config.yaml). CANDIDATE #2 (t-012, operator question): 70B
  middle-groq as scout — attempt 1 FAILED 0/7 on the permissive
  profile with a fully FABRICATED Trail block; attempt 2 (hardened
  profile) exposed a HARNESS BREAK: streaming tool-call deltas do
  not survive the Pi<->litellm<->groq path (direct non-streaming
  request returns proper tool_calls; ollama_chat streaming works).
  Model verdict INCONCLUSIVE pending the fix. QUEUED (tooling,
  builder-class): investigate/fix streaming tool-calls for groq
  through the proxy (candidates: litellm upgrade, Pi provider
  compat field, non-streaming mode); then RE-EXAM both candidates
  on the hardened profile (qwen3:4b FAIL stands meanwhile — its
  tool path was smoke-proven and the fabricated-verified claim
  disqualifies regardless). Local scout otherwise CLOSED until a
  stronger local candidate fits 6GB VRAM; Pi builder profile on
  builder-groq blocked by the same streaming break — same queue
  item. Working recipe, hardened scout profile and known breaks
  persisted in gateway/PI_HARNESS.md (session scratchpad does not
  survive sessions).
- GSD Pi adoption plan (operator-ordered deep-dive 2026-07-09;
  facts + mechanism inventory in RELATED_WORK «GSD Pi deep-dive»;
  verdict: EXTRACT mechanisms, do NOT adopt the agent — it would
  replace the Lead coordinator and forfeit the cost-crossover loop
  that is our niche). Items in priority order:
  - A1 zero-tool-call guard (builder-class, small; WHEN: next
    builder dispatch, BEFORE any further entrance/re-exam run —
    the t-015 retry qualifies if it slips past one more session):
    post-run check of a Pi worker transcript/requests.db — zero
    structural tool calls + substantive answer => automatic
    rejected-stamp before Lead reads the report. Deterministic
    detector for the F-14 fabrication class (exact t-011/t-016
    shape). DoD: script + tests + retro-run on the t-016 transcript
    reproducing FAIL. Prior art: GSD Pi v1.3.0 zero-tool-call guard.
  - A2 gateway fallback chains (builder-class, config-sized; WHEN:
    with/before the t-015 retry or the next Groq-quota incident,
    whichever first): litellm NATIVE fallbacks on the groq aliases
    for 429 TPM/TPD (t-013/t-015 class «Pi prompt weight vs
    free-tier ceilings»); D-0030 ordering — try native before
    building. Same item: evaluate Pi prompt-slimming (skills/tools
    trim) against the 8k TPM ceiling; GSD's budget-mode token
    profile is the prior art. Absorbs B2 (see below): litellm
    native BUDGETS/rate-limits per alias — quota rationing as a
    code wall, not session memory (D-0063).
  - A3 dispatch context manifest (Lead-class, mechanism — full
    rule-10 treatment; WHEN: next D-0054/rule-11 touch, not a
    dedicated pass): the dispatch text enumerates the exact
    files/data injected into the worker (GSD UnitContextManifest as
    prior art) — makes inject-vs-recon choices auditable and cuts
    worker context cost.
  - A4 Rule-6 deterministic check (Lead-class; WHEN: first weekly
    calibration): journal scan «two rejected, same task_id + tier,
    no escalated» — mechanical enforcement of rule 6, GSD's
    consecutive-dispatch caps as prior art. NOT a new tool: fold
    into the deterministic counting script for checks 3/13 already
    queued under the D-0053 follow-up.
  - A5 witness auto-collection (builder-class; WHEN: once the Pi
    builder profile is unblocked — after A2 clears the TPM path):
    wrapper runs the canonical pytest form after a Pi builder
    session and attaches verbatim output as a witness DRAFT (GSD
    verification_commands + canonical-verdict-field analog);
    acceptance itself stays with Lead (D-0037).
  - B-series (D-0063 two-layer enforcement, operator-confirmed
    2026-07-09: code guarantees the encounter with a rule, AI
    judges fulfillment in meaning — the selection axis for
    everything above):
  - B1 journal validator, OS repo (builder-class; WHEN: next
    builder batch, natural pair with A1): pre-commit validation of
    NEW routing-log.jsonl lines — D-0053 typed fields (attempt/
    failure_class on rejected, witness on builder-accepted, model
    presence), task_id novelty (t-NNN max+1, D-0060), D-0058
    acceptance matrix as code (acceptor tier above worker, or
    critic-input/queued-to-Lead flag present). REVISES the D-0060
    choice of manual tail re-read — on F-23 evidence (collision
    already happened here) + D-0063, recorded, not silent. Sibling
    implementation: AO3 scripts/log_append.py (ось 1).
  - B2 — FOLDED into A2: gateway budget walls are the same commit
    class (litellm NATIVE budgets/rate-limits per alias; evidence:
    t-015 TPD exhaustion — 98.5k/100k burned by earlier tasks
    before the exam got one token out).
  - B3 SessionStart hook (Lead spec -> builder; WHEN: after the
    first weekly calibration validates what the Boot Report line
    should show — same gating logic as the checks 3/13 counting
    script): print actual model tier + open degradation window
    (journal tail) + calibration staleness at session start, making
    the D-0056 entry check unmissable (F-21/F-22 evidence).
    Mechanism commit at build time -> full rule-10 then.
  - NOT adopted (recorded to stop re-litigating): GSD as
    coordinator (duplicates Lead), auto-mode SQLite state machine +
    crash recovery (inseparable from their runtime; our analog is
    session handoff), supply-chain audit tags (no third-party-dep
    loop in this repo today), WXP (not confirmed in official docs).
- One-time rule-10(b) sweep of pre-SIBLING_MAP decisions
  (D-0028..D-0043 never had an axis sweep; F-12/F-13/F-14 were their
  unswept siblings). Point-lookup matrix per the map, NOT a rescan.
  EXTENDED by D-0064 (operator direction 2026-07-09): the SAME pass
  asks question (г) of EVERY decision D-0028..D-0063 — one line per
  mechanism (чем триггерится / какой код на пути, либо «на
  дисциплине» + названный детектор); gaps land as queue items
  (B-series class, D-0063 promotion by evidence), not immediate
  builds. Schedule: with/after the first weekly calibration. Rule-10(a)
  retro-audit deliberately NOT queued: its data stream is cc_usage,
  covered by calibration check 11.
- Evidence-acceptance adoption plan (F-17 + pi-autopilot priors in
  RELATED_WORK "Agent orchestration"; operator-approved 2026-07-08):
  - Stage 1 DONE 2026-07-08: D-0052 (witness on builder-accepted,
    `defect_found` event, failure-class word in rejected notes —
    absorbs eval-stage-1 item (1)); CLAUDE.md + roles both deploys,
    AO3 log_append.py vocabulary + tests, calibration check 13.
  - Stage 1.5 DONE 2026-07-08: D-0053 typed journal fields (F-18,
    external review by pi-autopilot author: task_id / attempt /
    failure_class / witness / ref; AO3 log_append enforce + tests;
    checks 3/13 amended). Queued from it: deterministic counting
    script for checks 3/13 (Lead spec -> builder, AFTER the first
    manual calibration validates what it should compute); structured
    worker-report frames deferred until dispatch volume (Rule #1).
  - Stage 1.6 DONE 2026-07-08: D-0054 tier-shaped DoD in EVERY
    dispatch (rule 11 both deploys + all three role files; F-19 —
    the draft was builder-only, operator's axis-3 question widened
    it before commit; detector = failure_class=spec stream,
    check 13(г)).
  - Stage 1.7 DONE 2026-07-08: D-0055 (F-20) — rule 10(b) answered
    by ENUMERATION over the current map's axes (axis list parsed
    from SIBLING_MAP at each run, never hardcoded) + commit-msg gate
    in both repos (.githooks + mechanism_gate.py twins; hooksPath
    set). First full-discipline dispatch cycle on the gate itself:
    t-001 delegated(critic) -> rejected (confirmed blocker F-A:
    diff-quoted skip syntax self-bypassed the gate) -> fixed with
    regression tests -> accepted. Detector: check 8 (hooksPath
    liveness + skip-line audit).
  - Stage 2 LANDED 2026-07-09 as D-0060, fired by the first real
    parallel-session incident (F-23: task_id t-008 allocated to two
    unrelated tasks by concurrent sessions): rule 4 addendum (owned
    paths, both for parallel specs and parallel sessions) + task_id
    allocation by journal-tail re-read at write time; detector =
    check 13(д). AO3 log_append.py enforce LANDED 2026-07-09
    (t-009, AO3 commit 5a26fe3: full-match t-NNN max+1, --reopen-task
    on closed ids, descriptive ids free; TOCTOU accepted best-effort,
    residual detector = check 13(д)). F-C/F-D hardening LANDED via
    t-010 (2026-07-09) — the first agentic API-contour dispatch
    cycle: builder->middle-groq through the gateway (operator pilot),
    2 attempts (rejected capability + accepted with documented
    Lead repairs), $0.0035 accounted real traffic, witness 262
    passed. Update Rule 4 datapoint recorded in the journal.
    Follow-up (operator direction, same day): builder-groq alias
    added to gateway/config.yaml — gpt-oss-120b as the CANDIDATE
    API-contour builder binding (judge twin, 13/13 incl. the
    code-tracing pair the 70B failed); next text-shaped cycles
    dispatch there, binding decided on journal evidence (D-0028).
    Caveat pinned in config: same model as judge -> Shadow Eval on
    this binding is self-judging, chief-judge review required.
  - Stage 3 (data-gated: only if first calibration's checks 10/11
    show the context/overhead discipline actually leaks): PreToolUse
    hook as context_budget analog — Lead spec -> builder implements
    -> critic review per rule 3. Do NOT build before that evidence
    (Rule #1).
- Eval plan, stage 1 (Habr evals articles 2026-07-08; priors in
  docs/RELATED_WORK.md "Evals"; operator-approved): (1) failure-class
  word in rejected-event notes (spec / capability / recon / tooling)
  — LANDED with D-0052;
  (2)+(3) LANDED 2026-07-09 as D-0057: PROCESS/SCOUT_GOLDEN_SET.md
  (7 questions incl. negative usage-vs-mention and judgment-refusal
  traps, pinned keys with verify commands, baseline t-006 7/7 PASS)
  + regression rule on agent-prompt edits, detector = calibration
  check 14. Queued from it: AO3 port of D-0057 (rule + set for the
  three shared tiers on next role-file touch; the 13 QA-pipeline
  agents decided separately on pipeline data — axes 1/6); critic
  golden set (candidate design: diff with seeded defects; build
  only if calibration shows critic drift, Rule #1).
- Eval plan, stage 2 (needs >=1 week routed traffic): journal's
  accepted tasks as a regression set replayed on the API contour on
  model/price changes; minimum-n / pass^k in DELEGATION_TABLE Update
  Rules (thresholds from first-calibration data); numeric judge-human
  agreement in JUDGE_CALIBRATION_PROTOCOL. NOT taken: per-PR CI, full
  execution-based bench harness (Rule #1).
- AO3 adaptation of the session-handoff skill (D-0050): its boot
  path is CLAUDE.md + docs/HANDOFF.md + state/, no BOOT.md.
- AO3 CLAUDE.md boot-diet trim (D-0051 pairing duty, next touch):
  operative content is already in sync; narrative trim analogous to
  this repo's 2026-07-08 diet.
- White Paper: Architect review IN PROGRESS (started 2026-07-07).
  Comment 1 addressed same day (v0.1.1). Portability + contour
  asymmetry FOLDED IN 2026-07-09 (v0.1.2, §4.1 + §5.1, operator-
  ordered). Still queued: §7 upkeep against the evidence log; full
  sync with D-0034..D-0038 once the unified plan's first steps land;
  fold the D-0062 Two-Vocabularies bridge into §4.1 (functions vs
  grades).

## Environment Notes (this machine)

- Ollama 0.31.1 (winget); NVIDIA driver 582.28 — Qwen3-4B runs 100%
  on the GTX 1060 GPU (~5 s warm vs ~15 s CPU).
- Proxy must be started from gateway/ (callback imports are
  cwd-relative). litellm does NOT auto-load gateway/.env — export
  GEMINI_API_KEY / GROQ_API_KEY before starting the proxy.
- lead-gemini = gemini/gemini-2.5-flash (2.0-flash has ZERO free-tier
  quota on this key — 429, don't use it). Gemini free tier is
  5 req/min.
- lead-sonnet alias (anthropic/claude-sonnet-5) exists in config.yaml
  but is unused: no ANTHROPIC_API_KEY in this environment.
- Free-telemetry mode: intern/analyst (Ollama) carry synthetic
  Haiku-class accounting prices, so Guard/Ledger money paths work at
  $0 cash.
- Open operational item (Architect): route real API-contour traffic
  through the gateway; lead needs ANTHROPIC_API_KEY (paid).
- BSOD 2026-07-09 15:02 (bugcheck 0x3B in aehd.sys — Android
  Emulator Hypervisor Driver, minidump 070926-7359-01.dmp) while
  the AO3 pipeline exercised the emulator; gateway/Pi processes were
  idle userspace (no intern request had reached the proxy). Rule of
  thumb recorded: do NOT run the Android emulator (AO3 QA pipeline)
  and local GPU inference (Ollama exam runs) simultaneously on this
  machine; sequence heavy workloads. The AO3 session died with
  uncommitted work — its next boot must record the dirty tree per
  Boot Report rule 6.

## Archive (D-0038 pointers)

Closed work lives in docs/task_reports/ (index in its README.md):

- 2026-07-03_shadow-evaluation-and-llm-judge.md — first Shadow
  Evaluation runs; judge build, contamination and judge-bias lessons.
- 2026-07-03_research-notes.md — related-work priors (canonical:
  docs/RELATED_WORK.md).
- 2026-07-04_white-paper-iteration.md — White Paper v0.1 log, Phase 2
  gate definition, external review recording.
- task-1-2_cost-accounting-and-traffic-kind.md — Tasks 1-2 (ACCEPTED
  2026-07-07).
- task-4_test-isolation.md — Task 4 (ACCEPTED 2026-07-07).
- task-5_usage-report.md — Task 5 (ACCEPTED 2026-07-07), full
  strategic findings text.
- task-6_subagent-transcripts.md — Task 6 (ACCEPTED 2026-07-08),
  sidechain telemetry, spec errata.
- task-7_agent-attribution.md — Task 7 (ACCEPTED 2026-07-08), first
  critic dispatch, per-agent cost breakdown unlocked.
- task-3_phase2-readiness.md — Task 3 (ACCEPTED 2026-07-09), Phase 2
  readiness digest, first gate-criteria readout (G1/C2 met, R1 not
  met, rest honest gaps).
- 2026-07-08_routing-dogfooding-day.md — interim 18h read, dead-tier
  revival, F-1 formalization, first degradation cycle, mechanism day
  (F-12..F-16 / D-0044..D-0051).

This file is intended to be updated frequently.
