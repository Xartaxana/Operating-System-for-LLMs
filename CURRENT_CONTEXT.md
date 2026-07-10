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

t-015 llama-70B re-exam, attempt 4 — the one open exam of the
local-scout thread (t-013 closure, t-016 re-exam FAIL and the
2026-07-09 mechanism-day narrative: archived —
docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md):

- t-015 llama-70B re-exam: attempts 1-3 ALL aborted by Groq TPD
  (rejected/tooling x3, NOT model verdicts). Attempt 3 ran 2026-07-10
  02:18 as first Groq traffic of the "fresh" window and died on turn
  2: rolling 24h still held Used 90,614 - the 429 hint frees room for
  ONE request, not a multi-turn exam; yesterday's bulk (~68k, t-013
  traffic in side-DB t013.db) falls out only ~18:56 today. F-27
  registered: the t-018 wall counts requests.db ONLY (saw 14,175),
  side-DB/off-proxy traffic is invisible to it - the check-13
  (в)-detector fired exactly as registered at t-018 acceptance.
  Behavioral positive again: 5 REAL tool calls on the hardened
  profile, guard t-017 INCONCLUSIVE (ops abort) applied before
  grading. ATTEMPT 4 (Lead decision at attempt-3 rejection): TODAY
  >=19:15 local, pre-flight probe authorized (<=3 minimal middle-groq
  requests through the proxy; a probe 429 yields exact Used numbers),
  launch only with headroom ~70k. Recipe unchanged: hardened profile
  + Pi call form = gateway/PI_HARNESS.md (break #3 has the
  window-math addendum); 7 questions verbatim =
  PROCESS/SCOUT_GOLDEN_SET.md (keys re-verified 2026-07-10, Q3 line
  numbers refreshed); proxy carries the wall (started 02:16, keep or
  restart per PI_HARNESS); journal as t-015 attempt 4.
- t-019 quota_events digest line — DONE 2026-07-10, archived
  (docs/task_reports/2026-07-10_queue-closures-archive.md).

Standing reminder for the first calibration: tier-check the D-0059
commit's session per D-0058 (checks 5/6, F-23 context in the archive
above).

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (commit 171078c; closed
  the last open item of Phase 1.5 step 2). Later policy changes
  follow the normal mechanism discipline.
- Evidence stream: logs/routing-log.jsonl (t-001..t-022 so far); ALL
  table statuses estimated — counts and status moves belong to the
  first weekly calibration (Update Rule 1, D-0047).
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
  Second judge judge-gemini (gemini-3.5-flash, 13/13, t-023) —
  cross-family point work only (20 req/day): builder-groq
  self-judging pairs.
- Gemini key role exam DONE 2026-07-10 (t-023/t-024, operator
  order): pro tiers zero free quota; 3.5-flash Lead-REJECTED
  operationally (20 req/day) -> judge-gemini; 2.5-flash (lead-gemini)
  12/13 + B-exam passed -> API-contour Lead-baseline CANDIDATE
  (status moves await weekly calibration). Evidence:
  docs/task_reports/2026-07-10_gemini-key-role-exam.md.
- traffic_kind tagging live: real/synthetic/replay/judge; gate G1
  counts only 'real'. The tag travels via extra_body metadata —
  litellm's metadata= kwarg does NOT reach the wire (verified; see
  comments in sqlite_logger.py / shadow_eval.py).
- Tests: suite 159 passed (2026-07-10 witness, t-019 acceptance;
  canonical form python -m pytest tools/ gateway/ -q).
  gateway/conftest.py isolates every test (tmp DB + full litellm
  callback-list snapshot/restore — restoring litellm.callbacks alone
  is NOT enough, litellm copies the logger into six lists at call
  time).
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
- Local scout / gateway-worker harness evaluation: CLOSED 2026-07-09
  except the t-015 attempt-3 exam (see Current Task). Standing
  verdicts: Pi harness ADOPTED for gateway workers (recipe + known
  breaks: gateway/PI_HARNESS.md; survey: RELATED_WORK «Agent tool
  harnesses»); qwen3:4b FAILED entrance + hardened re-exam (0/7 x2,
  fabrication) — local scout CLOSED until a stronger local candidate
  fits 6GB VRAM; row «recon -> local intern» does NOT enter the
  table; scout-tier economics ~zero ($1.33 all-time), standing case
  is resilience + the API-contour second pilot needing recon. Pi
  builder profile blocked by builder-groq TPM 8000 vs Pi prompt
  weight — unblock path = prompt-slimming eval (A2 remainder below).
  Full narrative (steps 1-3, t-011/t-012 exams, infrastructure
  lessons): archived —
  docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md.
- GSD Pi adoption plan (operator-ordered deep-dive 2026-07-09;
  facts + mechanism inventory in RELATED_WORK «GSD Pi deep-dive»;
  verdict: EXTRACT mechanisms, do NOT adopt the agent — it would
  replace the Lead coordinator and forfeit the cost-crossover loop
  that is our niche). Items in priority order:
  - A1 zero-tool-call guard (t-017) + A2 quota walls (t-018) — DONE
    2026-07-09, archived with accepted limitations
    (docs/task_reports/2026-07-10_queue-closures-archive.md).
    OPEN remainders from A2: Pi prompt-slimming evaluation
    (skills/tools trim) against the builder-groq 8k TPM ceiling
    (GSD budget-mode token profile as prior art);
    requests(model,ts) index candidate (Rule #1: only on latency
    evidence — spent_today shares the full-scan cost).
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
  - B2 — FOLDED into A2, closed with it (archived same file as A2).
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
- Boot-diet — RESOLVED for now (D-0067, Architect decision
  2026-07-10; morning pass and re-breach history archived —
  docs/task_reports/2026-07-10_queue-closures-archive.md). Round 1:
  archiving pass restored 99,775 < 100KB. Round 2 (D-0067): boot
  reads ARCHITECTURE_BOOT.md (~4KB core; full spec on demand),
  Shadow Evaluation Log relocated to docs/SHADOW_EVALUATION_LOG.md —
  boot path measure recorded in the D-0067 commit. CLAUDE.md
  deliberately untouched (worst win/risk ratio — policy dies out of
  context, F-1/F-9). Standing duty: re-measure at every handoff
  (D-0050 check 4, breach-response ordering fixed 2026-07-10).
- One-time rule-10(b) sweep of pre-SIBLING_MAP decisions
  (D-0028..D-0043 never had an axis sweep; F-12/F-13/F-14 were their
  unswept siblings). Point-lookup matrix per the map, NOT a rescan.
  EXTENDED by D-0064 (operator direction 2026-07-09): the SAME pass
  asks question (г) of EVERY decision D-0028..D-0063 — one line per
  mechanism (чем триггерится / какой код на пути, либо «на
  дисциплине» + названный детектор); gaps land as queue items
  (B-series class, D-0063 promotion by evidence), not immediate
  builds. Further extended by D-0065 (F-25): the same pass HUNTS
  already-born UNRECOGNIZED mechanisms through the net's homes
  (ARCHITECTURE.md, BOOT.md, gateway/PI_HARNESS.md, PROCESS/,
  roles/skills; first named candidate: PI_HARNESS hardened scout
  profile rule 0, born at t-012 without the four questions) — each
  find gets the four questions backfilled or an explicit
  «не-механизм» verdict. Schedule: with/after the first weekly
  calibration. Rule-10(a)
  retro-audit deliberately NOT queued: its data stream is cc_usage,
  covered by calibration check 11.
- Evidence-acceptance adoption plan (F-17): stages 1 / 1.5 / 1.6 /
  1.7 / 2 DONE 2026-07-08..09 (D-0052..D-0055, D-0060; stage details
  archived —
  docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md).
  Live residuals: deterministic counting script for checks 3/13
  (Lead spec -> builder AFTER the first manual calibration);
  structured worker-report frames (deferred until dispatch volume,
  Rule #1); builder-groq = CANDIDATE API-contour builder binding —
  next text-shaped cycles dispatch there, binding decided on journal
  evidence (D-0028; self-judging caveat pinned in config.yaml).
  Stage 3 (data-gated: only if first calibration's checks 10/11
  show the context/overhead discipline actually leaks): PreToolUse
  hook as context_budget analog — Lead spec -> builder -> critic per
  rule 3. Do NOT build before that evidence (Rule #1).
- Eval plan, stage 1 — LANDED (D-0052 + D-0057; details archived —
  same file as above). Live residuals: AO3 port of D-0057 (rule +
  set for the three shared tiers on next role-file touch; the 13
  QA-pipeline agents decided separately on pipeline data — axes
  1/6); critic golden set (candidate design: diff with seeded
  defects; build only if calibration shows critic drift, Rule #1).
- Eval plan, stage 2 (needs >=1 week routed traffic): journal's
  accepted tasks as a regression set replayed on the API contour on
  model/price changes; minimum-n / pass^k in DELEGATION_TABLE Update
  Rules (thresholds from first-calibration data); numeric judge-human
  agreement in JUDGE_CALIBRATION_PROTOCOL. NOT taken: per-PR CI, full
  execution-based bench harness (Rule #1).
  - Batch API candidate (added 2026-07-10, operator-approved):
    judge/replay/golden-set traffic = independent request sets with
    no latency need — exactly the Message Batches profile (-50% on
    input AND output tokens; most batches <1h, SLA 24h; results keyed
    by custom_id; Groq/Gemini have analogs). TRIGGER (Rule #1, build
    nothing before): ANTHROPIC_API_KEY lands AND stage-2 regression
    replays run regularly — free-tier judge traffic gains $0 from the
    discount today. At adoption: batch endpoints bypass the proxy's
    request logging — the accounting path into requests.db must land
    in the same move (axis 2, never a silent $0). Interactive/agent
    sessions stay off batch by nature (dependent-call loops).
- AO3 session-handoff skill — DONE 2026-07-10 (t-021, AO3 commit
  0911cf6), archived
  (docs/task_reports/2026-07-10_queue-closures-archive.md).
- AO3 CLAUDE.md boot-diet trim (D-0051 pairing duty, next touch):
  operative content is already in sync; narrative trim analogous to
  this repo's 2026-07-08 diet. SAME touch: port the rule-1 amendment
  (D-0066 two-pass external surveys) — axis-1 remainder of the
  2026-07-10 commit; port the breach-response ordering into AO3
  session-handoff check 4 (archive sweep FIRST, deep-cut queue item
  only after — added to the OS skill 2026-07-10, axis 1).
- OpenClaw adoption plan (survey 2026-07-10, t-022 + Lead second
  pass — first D-0066 application; facts and full plan: RELATED_WORK
  «OpenClaw survey»). No standalone builds; each item rides an
  already-queued vehicle: (1) per-file boot-budget breakdown (raw vs
  injected + truncation flag, `/context list` as prior art) — into
  session-handoff check 4 on next skill touch AND into B3
  SessionStart hook when built; (2) quota-wall reconciliation with
  provider-reported rate-limit headers (Groq) — TRIGGER FIRED
  2026-07-10 (t-015 attempt 3 / F-27: wall saw 14k, Groq 90.6k —
  side-DB t013.db invisible to it); build with the next builder
  batch, natural pair with B1; (3) lane-contract
  fields (Owns/Non-goals/Handoff) — into the A3 dispatch manifest
  template when A3 lands. Recorded as prior art, no work: strict
  selection (validates t-018 no-fallback), two-stage failover +
  cooldown ladder (design ready if a second Groq/Gemini key appears),
  gateway-process cron with per-job model (design source for the
  batch-Lead mode if operator wants it mechanized). NOT adopted:
  channels, delegate identity, compaction/memory (harness-owned),
  utilityModel (duplicates D-0062 function→model).
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
- lead-gemini = gemini/gemini-2.5-flash (10 req/min, 250 req/day);
  judge-gemini = gemini/gemini-3.5-flash (5 req/min, 20 req/day
  rolling — pace >=13s, point work only). ZERO free quota on this
  key: 2.0-flash and ALL pro tiers (3.1-pro/3-pro/2.5-pro) — 429,
  don't use (probed 2026-07-10).
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

## Archive (D-0038 pointer)

Closed work lives in docs/task_reports/ — the annotated index is its
README.md (single owner since 2026-07-10; per-file descriptions were
duplicated here and are trimmed from the boot path).

This file is intended to be updated frequently.
