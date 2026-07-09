# 2026-07-09 — Pi-worker exams, t-013 closure, adoption-plan stages (boot-diet archive)

Archived from CURRENT_CONTEXT.md on 2026-07-10 during the D-0038
boot-diet pass (boot path breached the 100KB threshold at the
2026-07-09 handoff: 104,052 bytes; 105,374 at archiving time). The
blocks below are VERBATIM as they stood in CURRENT_CONTEXT.md when
archived; the live remainders (t-015 attempt 3, queue residuals)
stayed in CURRENT_CONTEXT.md with pointers here. Related journal
events: t-011..t-019 in logs/routing-log.jsonl; related archives:
2026-07-08_routing-dogfooding-day.md.

## Current Task narrative — t-013 closure and re-exams

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
commit's session per D-0058 (check 5/6).

## Queue item — Local scout evaluation (closed except t-015 attempt 3)

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

[Continuation, journal t-013..t-018: the streaming break did NOT
reproduce (t-013); re-exams ran 2026-07-09 evening — t-016 qwen3:4b
FAIL 0/7 confirmed on the hardened profile; t-015 llama-70B attempts
1-2 aborted by the ROLLING Groq TPD window (rejected/tooling x2,
rule-6 escalation), attempt 3 queued as first Groq traffic of a fresh
window; A1 zero-tool-call guard (t-017) and A2 quota walls (t-018)
landed as mechanism commits the same evening.]

## Queue item — Evidence-acceptance adoption plan, stages 1..2 (DONE)

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

## Queue item — Eval plan, stage 1 (LANDED)

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
