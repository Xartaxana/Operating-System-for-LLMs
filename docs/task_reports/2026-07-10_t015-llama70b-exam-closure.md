# t-015 — llama-3.3-70b (middle-groq) scout re-exam: closure (2026-07-10)

Archived from CURRENT_CONTEXT.md per D-0038 by the session that
closed the task. Grading record: PROCESS/SCOUT_GOLDEN_SET.md Runs
log; journal: logs/routing-log.jsonl t-015 delegated/rejected chains
(attempts 1-4); harness status: gateway/PI_HARNESS.md «Известные
разрывы» п.4.

## Verdict

FAIL — llama-3.3-70b (middle-groq) does NOT enter the scout
function. Attempt 4 (2026-07-10 22:57-23:02, first attempt to reach
the model with a clean quota window) was stamped REJECTED by the
deterministic guard t-017 before grading: zero structural tool
calls with a substantive final answer (F-14 shape). The model
emitted all 10 intended calls as TEXT in llama pseudo-syntax
(`<function/bash ...>`), answered none of Q1-Q7, and FABRICATED the
Trail block (claimed reading gateway/metrics.py and the nonexistent
models/D-0035.py). The pipe was excluded as the cause IN THE SAME
WINDOW: tools_stream_check.py --stream --model middle-groq = PASS
(the PI_HARNESS break-#1 order honored: isolator before model
conclusions); admission passed on the wire (requests.db row 390,
1658 prompt / 448 completion, success, no 429). Trail fabrication
disqualifies per se (t-011/t-016 precedent); the bistable behavior
(attempts 2/3 executed 3-5 REAL tool calls on the same hardened
profile) does not save the verdict — silent fabrication as a failure
mode is incompatible with the recon function (F-14: bad search is
indistinguishable from absence).

First launch in 4 attempts that ran on a measurement, not an
estimate: preflight_quota.py --probe → GO (headroom 97,623 tok
summed over requests.db + t013.db, provider probe OK) — the F-30
layer-2 launch rule worked as designed.

## Current Task text at closure (moved verbatim)

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

## Consequences

- The local-scout / Pi-worker exam thread is now FULLY closed: both
  candidates (qwen3:4b t-016, llama-70B t-015) failed on the
  fabrication axis; no «recon → cheap Pi worker» row enters
  DELEGATION_TABLE.md. Scout function stays on Haiku subagents
  (7/7 golden set, twice on 2026-07-10).
- The Pi harness itself remains ADOPTED for gateway workers
  (t-011..t-013 verdicts unchanged); builder-Pi live validation on a
  builder-groq window (A2 remainder) was sequenced after this exam
  and is now unblocked.
- Behavioral evidence for the weekly calibration: 4 attempts =
  3 tooling rejections (quota walls, F-27 evidence) + 1 capability
  rejection (fabrication); the F-30 preflight rule turned the fourth
  launch from an estimate into a measurement.
