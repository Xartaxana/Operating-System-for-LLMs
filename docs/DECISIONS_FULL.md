# Decisions Log — Full Texts (D-0051)

Canonical full texts of all decisions: rationale, history, rule-10
answers. The boot path loads only the one-line index (DECISIONS.md);
this file is point-read on demand. New decisions add BOTH the index
line and the full text here in the same commit; the entry counts of
the two files must match (calibration check 12).

## D-0001
Git is the single source of truth.

## D-0002
English is the canonical project language.
Russian is a synchronized translation.

## D-0003
Engineering over Perfection.

## D-0004
The project consists of a White Paper, Architecture Specification and Reference Implementation.

## D-0005
Kernel must remain independent of any specific LLM.

## D-0006
Project memory is layered.

## D-0007
Every document must be reachable from repository navigation.

## D-0008
Every Patch must leave the repository in a consistent, navigable state.

## D-0009
Repository content overrides chat history.

## D-0010
BOOT.md defines the canonical repository loading sequence.

## D-0011
SYSTEM_PROMPT.md defines permanent behavioural rules.

## D-0012
Every commit must improve the repository as a complete knowledge system.

## D-0013
Recurring engineering practices must be documented as repository protocols.

## D-0014
No important project knowledge may remain only inside chat history.

## D-0015
The repository stores both project knowledge and engineering processes.

## D-0016
A commit should represent exactly one conceptual change.

## D-0017
Validate Before Elaborating.
Implement new architectural layers only after validating the previous ones.

## D-0018
Infrastructure Before Features.
Improve development infrastructure before relying on new capabilities.


## D-0019
Patch Format v2 is the standard modification format. Large documents should be modified incrementally instead of being fully overwritten.

## D-0020
Human assistance is a fallback mechanism. Every automatic repository access method must be attempted before requesting manual intervention.

## D-0021
The repository should be executable engineering memory. A new session should recover project state from the repository rather than chat history.


## D-0022
The success criterion for repository memory is a Zero Context Recovery Test. A new LLM session must be able to resume the project using only the repository.

## D-0023
Every repository boot must produce a standardized Boot Report. Boot success is determined by loading repository state rather than by subjective interpretation.

## D-0024
Phase 0 is complete only after a successful Zero Context Recovery Test and correction of all deficiencies discovered during that test.

## D-0025
The repository must always define exactly one current engineering task. LLMs should execute that task instead of inferring the next objective.

## D-0026
Direct git commits are the standard modification mechanism when the LLM has repository access. The patch mechanism (apply.py) is retained only as a fallback for environments without repository access.

## D-0027
Supervision of the Lead model is split by reliability requirements: Guard (deterministic budget enforcement, no LLM), Ledger (deterministic analytics, no LLM), Analyst (small LLM over telemetry, on demand). The cost of supervision must be measurably lower than the savings it produces.

## D-0028
Delegation decisions are driven by DELEGATION_TABLE.md. The initial table is estimated up front and refined continuously by Shadow Evaluation during implementation; a long measurement phase is explicitly rejected.

## D-0029
The Router is deferred until telemetry from Phase 1 shows what is worth routing.

## D-0030
Prefer existing open-source solutions over building custom ones whenever they fit the project's purpose. Custom code is written only where no suitable open-source component exists or where the component is the project's own contribution. Example: use LiteLLM as the gateway instead of writing a proxy.

## D-0031
The LLM judge is itself a supervised worker. Its verdicts are audited by a Lead-tier chief judge (escalation on table-status changes plus random per-run audits), reviewed pairs grow the calibration set, and the judge model is upgraded only on measured agreement degradation, never preemptively. See PROCESS/JUDGE_CALIBRATION_PROTOCOL.md.

## D-0032
Accounting prices, not cash prices. Every gateway alias carries a nonzero accounting price (the provider's paid-tier price for free-tier APIs, synthetic Haiku-class prices for local models); a free tier is a cash discount, not a cost of zero. Rule #1 (supervision must cost less than the savings it produces) is verified against accounting prices, and the accounted cost of every component — including the judge — must appear in the reports where delegation decisions are made.

## D-0033
Phase transitions are gated by explicit, telemetry-computable criteria recorded in ROADMAP.md, with numeric thresholds set up front and revised only through a DECISIONS.md entry. A gate turning green produces a written gate report; the Architect signs the transition. The first task of any newly opened workstream is an evaluation of an existing tool, never a build (extends D-0029, D-0030).

## D-0034
The operator's real Lead is the Claude Code subscription, and Claude Code transcripts (~/.claude/projects/**/*.jsonl) are a first-class real-traffic telemetry source alongside the gateway log. The external plan "routing in Claude Code" (2026-07-07) is merged into the roadmap as the Claude Code workstream (docs/UNIFIED_PLAN_2026-07-07.md): tiered subagents, routing policy, escalation journal, transcript-based usage reports. Subscription usage is accounted at API list prices (extends D-0032: a subscription is a cash discount, not a cost of zero). Gate G1's "real traffic" is amended accordingly: the operator's actual working traffic, measured at the gateway or from transcripts; synthetic, replay and judge traffic still never count.

## D-0035
Delegation statuses are a four-state model: estimated (expert prior), provisionally_validated (measured on synthetic or small samples), production_validated (measured on real traffic with sufficient volume and task-level cost), rejected (measured harmful). Adopted from the 2026-07-04 external review: rows previously marked "validated" from tiny synthetic samples are reclassified provisionally_validated — the label must not read stronger than the data. Status changes still require evidence (Update Rule 1); only production_validated rows may justify routing real traffic.

## D-0036
Phase 2's second workstream is Context Management Evaluation, not compression alone (adopted from the 2026-07-04 external review). Provider prompt caching, structured compaction, retrieval/memory and semantic response caching compete under Rule #1 through the same Shadow Evaluation loop. Evaluation order is fixed: cache-aware accounting first (raw vs cached vs paid-uncached input tokens), provider caching evaluated before any lossy compression, and code context stays exact by default. The C-gate repetition driver is measured net of provider caching: the lever must justify itself against what caching already delivers.

## D-0037
Delegation is flat: workers never spawn workers. Decomposing a task into independently executable parts, writing their specs and accepting the results belong to the coordinator role; parallelism is achieved by the coordinator dispatching several workers with independent specs (e.g. two builders on independent code parts, or a code-writer and a test-writer working from the same spec). A worker that discovers its task is decomposable escalates — "decomposable" is an escalation-journal category and evidence about the true tier boundary — instead of splitting the task itself. Rationale: decomposition quality is what the strongest tier is paid for, nested delegation destroys cost/evidence attribution (Rule #1, escalation journal), and ANTI_GOALS.md rejects maximizing agent count.

The coordinator role is not hard-wired to the Lead model. Dispatch (choosing a tier for an already-scoped task) is separated from decomposition (creating the scoped parts): dispatch is cheap — deterministic rules or a small model (this is the deferred Router, D-0029). Decomposition defaults to the strongest available tier; moving it to a cheaper tier (e.g. a judge-class reasoning model on contours where frontier orchestration is too expensive) is itself a delegation-table row — it enters as `estimated` and is promoted only on evidence (D-0028, D-0035), measured by total task cost including retry loops caused by bad splits (DELEGATION_TABLE.md Update Rule 4). An orchestrator model gets its own role alias so orchestration cost stays separable in the Ledger (same principle as judge-groq, D-0031/D-0032).

## D-0038
CURRENT_CONTEXT.md holds live state only; closed work is archived out of the boot path. Boot context is a paid resource — the project's own subject — so the boot sequence must not accumulate history. When a task or workstream closes (review ACCEPTED or Architect sign-off), the session that closes it moves the spec, execution report and review verbatim to docs/task_reports/ and leaves a one-line pointer in CURRENT_CONTEXT.md. Evidence is never deleted, only relocated; DELEGATION_TABLE.md's evidence log and DECISIONS.md are not subject to archiving. Archiving closed items is a standard Session End step (PROCESS/SESSION_PROTOCOL.md).

## D-0039
The Lead itself can degrade, and degradation must be explicit, scoped and reversible. Triggers: safety measures on the frontier model (e.g. Fable's dual-use restrictions refusing security-adjacent work that Opus handles), subscription limits, or model unavailability. On degradation the coordinator switches down one tier (Fable -> Opus -> Sonnet), records a `lead_degraded` journal event with the reason and the scope of the obstacle, and continues routine coordination. While degraded the coordinator does NOT change delegation-table statuses, does NOT sign gates, and queues architecture-level decisions for the restored Lead. Return is the default, not an option: at the next task boundary or session start the coordinator returns to the strongest available tier and records `lead_restored`; a degradation that must survive a session boundary is recorded in the routed project's journal/state — otherwise a fresh boot always assumes the full-strength Lead. Degradation events are telemetry: the weekly calibration loop reads them alongside escalations, and cc_usage shows what degraded work actually cost per tier.

## D-0040
Workers are dispatched in the background by default. A coordinator blocked waiting on a worker wastes the scarcest subscription-contour resource — Lead availability (wall-clock time and operator interactivity, not tokens): while a multi-hour worker runs, the Lead can plan, review other results, answer the operator, or dispatch parallel workers. Synchronous (blocking) dispatch is justified only when the coordinator's immediate next action depends on the worker's result AND no other useful work or operator interaction is pending (e.g. strictly sequential pipeline steps). The acceptance duty is unchanged (D-0037): every completed worker's result is reviewed when it arrives. Applies to both contours; on the API contour the same principle reads as async dispatch wherever the harness supports it.

## D-0041
Delegation on the subscription contour is opt-in, not emergent. The
default Claude Code harness does not initiate subagent dispatch on its
own ("Do not spawn agents unless the user asks" — finding F-1,
docs/FINDINGS.md, observed 2026-07-08): left alone, the coordinator
does delegable work itself on the most expensive tier. Therefore the
routing policy must auto-load into the coordinator's context in every
project where routing is expected (in Claude Code: the project's
CLAUDE.md); tier-agent definitions alone are insufficient — they
describe the tiers but do not prompt their use. "Deploying the routing
MVP" to a project means deploying three things together: the
auto-loaded policy, the tier agents, and the delegation journal.
Corollary for the White Paper: the production-harness default is
conservative (zero delegation), so the architecture's job on this
contour is raising delegation from zero to an evidence-governed level,
not restraining agent sprawl (ANTI_GOALS.md addresses the opposite
failure mode).

## D-0042
An explicit operator-initiated switch of the Lead model to a lower
tier is a lead_degraded trigger, alongside D-0039's original triggers
(safety refusals, subscription limits, unavailability). Journal event
types stay lead_degraded / lead_restored; the initiator and reason are
recorded in the event's notes field, not as a separate event type. The
journal is self-declaration: weekly calibration cross-checks declared
models against per-turn transcript telemetry (cc_usage), so a switch
nobody journaled (e.g. made before session start) still surfaces — the
discrepancy is itself a calibration finding. Switches up or sideways
are not degradation events and are currently untracked; tracking them
would be a new decision. First live cycle: 2026-07-08 (Fable -> Opus
4.8 -> Fable, logs/routing-log.jsonl).

## D-0043
Fix the class, not the instance. Operator directive (2026-07-08,
finding F-10): every tier and model was repeatedly caught patching the
found occurrence of a defect while leaving known analogous places
untouched and writing no general rule. Therefore closing ANY defect
requires three steps: (1) name the class — state what the general
failure is, not just the local symptom; (2) sweep the known analogous
places (the other deployment, the other contour, the sibling tiers,
the sibling documents/rules) and fix them now or explicitly queue or
journal what remains — a knowingly unfixed sibling left silent is a
violation, exactly as a silent skip is under F-9; (3) if a rule can
prevent recurrence, write it at the highest level that binds all
future instances (constitution > DECISIONS.md > deployment policy >
local file), never only in the file where the defect was found.
Division of duty follows D-0037: workers REPORT sibling defects they
notice (they do not expand scope themselves), reviewers check
class-completeness of every fix as a standard finding category, the
coordinator owns the sweep and the rule placement. Recorded in
SYSTEM_PROMPT.md (constitution, always loaded) because it must bind
any LLM in any session — routed or not.

## D-0044
Restoration from Lead degradation includes acceptance of the degraded
window. D-0039 specified entering degradation and returning from it
but left the return without a review step: work done while degraded
re-entered the mainline unreviewed — the degraded coordinator was
effectively the only worker in the system whose output bypassed the
D-0037 acceptance duty (gap found by an operator question, finding
F-12; the first live cycle 2026-07-08 confirms it — `lead_restored`
only unblocked the decision queue, the window's commit was never
reviewed). Therefore: on `lead_restored` the restored Lead reviews the
degradation window — the journal events and the diffs/commits produced
while degraded — as standard D-0037 acceptance, and the
`lead_restored` event's notes must state what was reviewed and the
verdict (an empty window is noted explicitly). Processing the
deferred-decisions queue is separate work and does not substitute for
this review. Rule 10 answers: (a) cost — one review per degradation
cycle, paid by the restored Lead in Lead-tier tokens; bounded by the
window itself, since the journal delimits which diffs are in scope (a
five-minute window costs minutes); (b) axes — the policy edit is
paired across both deployments' CLAUDE.md (axes 1/4), and the rule is
the axis-3 extension of the D-0037 acceptance duty to the role
"coordinator temporarily working at a lower tier"; (c) failure
detection — weekly calibration already reads the journal, and a
`lead_restored` event without a window-review note is mechanically
visible as a violation, same class as a silent skip (F-9).

## D-0045
Rejections are journaled; rule 6's escalation trigger is defined by
them. The escalation rule ("2 failed attempts -> tier up") had no
mechanical substrate: "failed attempt" was undefined (does a critic
rejection count?) and left no journal trace — the vocabulary had
`accepted` with no negative counterpart, so a silent third retry on
the same tier was invisible to calibration, and retry loops could not
be counted per task for Update Rule 4 (gap found by an operator
question, finding F-13). Therefore: a worker result rejected at
acceptance (blocking critic findings or the Lead's own check) IS a
failed attempt and is journaled as `rejected` (agent = the worker,
model required, notes: task, reason, attempt number). Two `rejected`
on the same task at the same tier make escalation mandatory; a third
attempt at that tier is a violation. Deliberately NO in-flight dollar
stop-loss: the subscription contour has no live per-task cost meter,
so the attempt counter is the cheap operational proxy for the cost
crossover ("cheap tier with retries costs more than the upper tier
outright"); the true crossover is measured weekly by Update Rule 4
from cc_usage + the journal. Rule 10 answers: (a) cost — one journal
line per rejection, written during an acceptance step that already
happens; paid by the Lead; (b) axes — policy text and event vocabulary
paired across both deployments' CLAUDE.md (axes 1/4); AO3's format
enforcement updated in the same change (scripts/log_append.py
ROUTING_EVENTS/MODEL_REQUIRED_EVENTS plus its test); the rule applies
uniformly to all tiers (axis 3); `rejected` supplies the journal side
of the loop count whose cost side lives in cc_usage (axis 2); (c)
failure detection — weekly calibration checks both directions
mechanically: two `rejected` without a subsequent `escalated` is a
violation, and an `escalated` with no `rejected` trail questions the
self-declaration.

## D-0046
Information workers are accepted by trail, not by trust. A scout
digest, a critic verdict and a judge label are claims, not artifacts:
without an attached trail they cannot be verified cheaper than
redoing the work, so the D-0037 acceptance duty had no executable
form for them — the digest was taken on faith (gap found by an
operator question, finding F-14; the judge half of the class was
already fixed by D-0031, scout was its unswept axis-3 sibling).
Therefore: (1) a scout digest must end with a Trail block — searches
run (patterns/globs/commands) and files read (paths); negative claims
("X exists nowhere") are valid only with the trail, since a bad
search is indistinguishable from absence; (2) the Lead accepts a
digest by checking coverage against the question and spot-checking at
least one load-bearing claim (mandatory for negative ones), noting
the spot-check in the accepted event; a digest without a trail is
`rejected` (D-0045); (3) a critic's ACCEPT verdict is itself a
negative claim ("no blocking findings") and requires its trail — what
was checked (files, traced scenarios, tests run); (4) downstream
attribution: when a later builder/critic failure traces back to bad
recon, the `rejected`/`escalated` notes name the digest as root
cause — this is the evidence stream for scout's delegation-table row,
which otherwise accumulates nothing even when scout is used. Builder
is outside the class: its output is code and tests, verifiable as
artifacts. Rule 10 answers: (a) cost — the trail is ~free (the worker
lists what it already did); the spot-check is one targeted read/grep
per digest, paid by the Lead, bounded to one claim; attribution is
notes in events already written; (b) axes — role files and policy
paired across both deployments (axes 1/4); the duty covers the
information-worker family uniformly: scout, critic, judge-per-D-0031
(axis 3); the API-contour counterpart is Shadow Evaluation /
chief-judge review, already in place (axis 2); (c) failure detection
— weekly calibration flags scout `accepted` events lacking a
spot-check note, and the downstream-attribution notes feed the scout
row; a trail-less digest surfaces immediately as `rejected`.

## D-0047
The calibration loop leaves a run record and has an external
staleness detector; its checks live in one executable protocol. A
rule-10(c) audit of all existing mechanisms (operator-commissioned,
finding F-15) showed that nearly every detection promise made by the
policy routes through "weekly calibration will notice it in the
journal/cc_usage" — while calibration itself had no schedule, no
mention in the session protocol, no record of ever having run, and
its checks were scattered across decision texts with no executable
list. A detector cannot detect its own absence. Therefore: (1)
PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md is the canonical home of all
mechanical checks — any new mechanism whose rule-10(c) answer is
"calibration will notice" must add its check there in the same
commit, or the answer is empty; (2) every calibration run ends with a
`calibrated` journal event (period, events reviewed, table-status
changes, boot-file line counts for the F-8 check); (3) the external
detector is the Boot Report's Last Calibration line
(BOOT_REPORT_PROTOCOL.md rule 5): NONE or older than 7 days with live
routed traffic = OVERDUE, visible to the operator at every session
start — a simpler, more frequent process watches the watcher. Rule 10
answers: (a) cost — one protocol read per weekly run; one journal
line per run; one Boot Report line per session; all bounded and
Lead-tier; (b) axes — the protocol is a single file in the OS repo
(like SIBLING_MAP: two copies would themselves diverge) and reads
both deployments' journals; the `calibrated` event is deliberately
NOT paired into AO3's vocabulary — it is only ever legitimate in the
OS journal where the delegation table lives, and AO3's format
enforcement should keep rejecting it; axis-2 counterpart on the API
contour is gateway/metrics.py digests, already in place; (c) failure
detection — the Boot Report line is the detector, and its absence
from a Boot Report is visible to the operator who reads every such
report (rule 4 of the boot protocol guarantees the report is read:
the session stops on it).

## D-0048
The sibling map is verified externally and shrinks as well as grows.
SIBLING_MAP.md had an add rule ("new symmetry -> new axis, same
commit") but no verification and no removal rule (gap found by an
operator question, finding F-16 — the third watcher-without-a-watcher
in a row after the journal and the calibration loop). A registry with
an add operation but no verify/remove operations monotonically
diverges from reality. Three streams, all external to the map: (1)
liveness — calibration check 12 verifies every concrete path named in
the map exists in both repos and the referenced mechanisms are still
in force; a dead path is a violation of the map's same-commit rule;
(2) completeness — by recurrence: a defect of an already-class-fixed
class surfacing OUTSIDE the places the map pointed to is a finding
about the MAP (missed or wrong axis), recorded in FINDINGS with the
axis fixed in the same commit as the defect; (3) growth — the map's
line count joins calibration check 10's counters, and axes die
symmetrically to their birth: when a symmetry disappears (deployment
closed, mechanism removed), its axis is removed in the same commit
that killed the symmetry. Rule 10 answers: (a) cost — check 12 is a
path-existence pass over a ~100-line file once a week; the recurrence
rule costs nothing extra (it fires during normal defect closing);
the growth counter is one number per run; (b) axes — the map is
single-copy by design (its own header: two maps would diverge), so
there is no deployment pair to edit; the AO3 reporting duty for new
axes already exists and is audited by check 9; the verify/remove
symmetry applies the same discipline to the map that the map applies
to everything else (axis 3 in spirit); (c) failure detection — checks
10 and 12 surface staleness and bloat in the `calibrated` record;
missed axes surface through the recurrence rule, and calibration
check 9 already verifies that finding-closing commits name their
axes.

## D-0049
Rule 10's question (c) is a lifecycle invariant, not a birth
formality. Operator directive (2026-07-08, after the F-12..F-16
series): every mechanism needs a verification system — old and new
alike. Reformulation: question (c) now reads "where is the failure
detector REGISTERED", and a mechanism is in force only while it has
either a check in PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md or an
external detector explicitly named in its own text (Boot Report,
operator at a gate, constructive impossibility of silent failure).
"Calibration will notice" without a check added to the protocol in
the same commit is not an answer (D-0047). A mechanism without a
registered detector is a wish, not a mechanism; discovering one is a
finding. Existing mechanisms were brought under the invariant by the
2026-07-08 audit (F-15) and the checklist it produced; new ones are
held to it by calibration check 8, which now verifies registration,
not just the presence of prose answers. Rule 10 answers for D-0049
itself: (a) cost — zero marginal at authoring time (the (c) answer
was already mandatory; registration is a line in the protocol that
D-0047 already required for calibration-routed promises); (b) axes —
rule 10 text is paired across both deployments' CLAUDE.md (axis
1/4), the protocol stays single-copy in the OS repo; (c) detector —
calibration check 8 verifies registration of every new decision's
detector; check 8's own failure is visible because the `calibrated`
event must reference the checks run, and the Boot Report watches for
calibration absence (D-0047).

## D-0050
Session close is checked symmetrically to session open. Operator
directive (2026-07-08): before ending a session, verify the handoff —
everything the next session needs is committed AND pushed, not only
written. Measurement that motivated it: the boot path (CLAUDE.md +
BOOT.md's 11 files) is ~99 KB / ~1700 lines (~30-35K tokens), and at
the time of the directive 25 commits in the OS repo and 14 in AO3
had never been pushed — a machine failure would have lost a full day
of policy work. Mechanism: the session-handoff skill
(.claude/skills/session-handoff/) runs at Session End
(SESSION_PROTOCOL.md): git clean+pushed in both repos, journal closed
(no unpaired delegated / lead_degraded), CURRENT_CONTEXT archived per
D-0038, boot budget measured against the previous run, boot chain
paths alive. Rule 10 answers: (a) cost — one run per session close,
a handful of wc/git commands, paid by the Lead; (b) axes — a NEW
axis-4 pair recorded in SIBLING_MAP the same commit (session close
<-> session open: a check added on one side must ask "and on the
other?"); the AO3 sibling is its existing HANDOFF discipline — a
skill adaptation for AO3's boot path (CLAUDE.md + docs/HANDOFF.md +
state/) is explicitly queued; (c) detector — registered per D-0049:
the NEXT session's Boot Report line "Working Tree at Boot"
(BOOT_REPORT_PROTOCOL.md rule 6) mechanically exposes a skipped
handoff (dirty tree or unpushed commits at boot = finding), and
calibration check 10 tracks the boot-budget numbers weekly.

## D-0051
The boot path is on a diet; DECISIONS.md is a one-line index.
Measurement 2026-07-08: the boot path (CLAUDE.md + BOOT.md's 11
files) was ~99 KB / ~1729 lines (~30-35K tokens) per session start,
re-sent with context accumulation. Operator-approved diet, three
moves: (1) DECISIONS.md on the boot path holds one line per decision
— the operative statement; full texts (rationale, history, rule-10
answers) live in docs/DECISIONS_FULL.md and are point-read on
demand. This amends D-0038's clause "DECISIONS.md is not subject to
archiving": nothing is deleted or summarized away — full texts
relocate off the boot path and the index preserves every decision's
operative content. A new decision adds BOTH the index line and the
full text in the same commit. (2) CURRENT_CONTEXT.md received its
overdue D-0038 archiving pass (the 2026-07-08 day narrative moved to
docs/task_reports/). (3) CLAUDE.md keeps operative rule text only;
history and rationale live in DECISIONS/FINDINGS by reference — F-1
caution respected: every operative norm stays in the autoloaded
text. Rule 10 answers: (a) cost — one extra line per new decision;
saves roughly half the boot payload every session start; (b) axes —
a new axis-4 pair DECISIONS.md <-> docs/DECISIONS_FULL.md (index <->
full, entry counts must match) added to SIBLING_MAP the same commit;
AO3's CLAUDE.md is not rewritten (pairing is by operative content,
which is unchanged; its own trim is the pilot's next-touch duty);
(c) detector — boot-budget counters in session-handoff step 4 and
calibration check 10 catch regrowth; calibration check 12 verifies
the index and DECISIONS_FULL entry counts match.

## D-0052
Acceptance is evidence-based in both directions (F-17; external
prior: pi-autopilot witness coverage, RELATED_WORK "Agent
orchestration with evidence gates"). The journal recorded negative
acceptance outcomes (D-0045) but let positive ones stay
self-certified: "tests pass" was accepted as a retelling, and work
that broke AFTER acceptance left no trace back to the tier that
produced it — the false-accept rate was uncomputable, so
DELEGATION_TABLE statuses could only move on defects caught at
acceptance time. Three vocabulary/procedure changes: (1) WITNESS on
builder acceptance — an accepted event for a builder dispatch must
carry (or explicitly reference in the worker's report) the actual
output of the verification run (test command + result), not a
retelling; a report without a witness is returned → `rejected`.
Symmetric to the D-0046 trail rule: an acceptance verdict is itself
an information-worker claim (F-17 class). (2) `defect_found` journal
event — the session that finds a defect in previously ACCEPTED work
writes it (agent = the original worker tier; notes: what broke +
reference to the original accepted dispatch by ts/task; model
optional — the original dispatch carries it). This gives calibration
the per-tier false-accept rate — the missing downward evidence
stream for Update Rule 1. (3) Failure-class word in `rejected` notes
(spec / capability / recon / tooling) — eval-plan stage 1 item (1),
merged here as the same vocabulary change: calibration sees WHERE a
tier breaks, not only that it broke. Rule 10 answers: (a) cost — one
paste of run output per builder acceptance, one journal line per
late defect, one word per rejection; paid by Lead at acceptance
time; negligible against the calibration data it makes usable.
(b) axes — axis 1: CLAUDE.md + builder/critic role files of both
deployments, AO3's log_append.py vocabulary + its tests (axis 6),
all same-day; axis 3: witness duty lands in the builder role file,
scout/judge/critic already covered (D-0046/D-0031); axis 4:
DECISIONS index + full text this commit. (c) detector — REGISTERED
(D-0049) as calibration check 13 same commit: accepted(builder)
without witness = violation; defect_found stream is counted into a
per-tier false-accept rate reported in the `calibrated` event notes;
rejected without a failure-class word = violation.

## D-0053
Load-bearing journal facts are typed fields, not prose (F-18;
external review by the pi-autopilot author, relayed by the operator:
"you missed structured output"). The critique landed on hour-old
D-0052: the defect_found -> accepted link, the rule-6 "two rejected
on one task" counter, witness, failure class and attempt number all
lived inside the free-text notes field — so calibration checks
3/6/13 could only be executed by Lead-tier prose reading, while
their nature is "Ledger (no LLM)" per our own delegation table.
Vocabulary: `task_id` — a per-task identifier threading
delegated/accepted/rejected/escalated/defect_found (required for
those events); `attempt` (integer) and `failure_class`
(spec/capability/recon/tooling) on rejected; `witness` (actual
verification-run output) on builder-accepted; `ref` (the original
accepted's task_id) on defect_found. `notes` remains the
human-readable surplus, never the carrier of gate-consumed facts.
The journal is append-only: pre-D-0053 events are NOT rewritten; the
first weekly calibration reads them manually. A deterministic
counting script for checks 3/13 is queued (builder to a Lead spec,
after the first calibration — the manual first run validates what
the script should compute). Structured frames for WORKER REPORTS
(Trail/verdict as schema blocks) are deliberately deferred until
dispatch volume justifies them (Rule #1); the sibling precedent
already exists on axis 6 (AO3 schemas/agent-output). Rule 10
answers: (a) cost — a few short typed fields per event the Lead
already writes; near-zero at write time, repaid by making three
calibration checks script-computable (check 11 overhead reduction);
(b) axes — axis 1: CLAUDE.md journal sections of both deployments +
AO3 log_append.py enforce + its tests (axis 6) same day; axis 4:
DECISIONS index + full text this commit; axis 3 untouched (fields
are the Lead's journaling duty, not the workers'); (c) detector —
REGISTERED: AO3 side, log_append.py rejects events missing required
fields (tested); OS side, calibration checks 3 and 13 consume the
fields and flag their absence on post-D-0053 events (protocol
amended same commit).

## D-0054
Every dispatch carries a tier-shaped DoD (definition of done):
what "done" means and how acceptance will verify it. External prior:
pi-autopilot author's advice relayed by the operator ("each task
needs a clear DoD with a verification plan, or the orchestrator
drifts and delivers broken work after days"); our spec practice
already did this (e.g. Task 3's Acceptance block) but no written
norm required it — the F-9/F-13 lesson is that unwritten practice
silently decays. Tier shapes: builder — acceptance criteria + the
verification run whose output becomes the witness (D-0052); scout —
the explicit question(s) and a completeness criterion ("X is nowhere"
is a valid outcome and requires the Trail, D-0046); critic — what to
review AGAINST: the dispatch attaches the spec/DoD of the work under
review, otherwise only generic quality is checkable, not fitness for
the task. A worker returns a DoD-less dispatch with questions before
starting work. Lead's own work is covered by existing mechanisms
(D-0025: the single current task carries acceptance; D-0047:
calibration runs against a checklist; D-0044: degraded-window
acceptance), the judge by its calibration set (D-0031), AO3's QA
pipeline agents by axis-6 machinery (schemas/agent-output +
transitions). History: the first draft of this decision was
builder-only; the operator's question "why only builder — we have
several layers" widened it before commit (F-19, tenth F-11 case —
an axis-3 sweep skipped at proposal stage). Rule 10 answers:
(a) cost — a few DoD lines per dispatch the Lead already writes when
specs are healthy; the worker-side return fires only on defective
dispatches and costs one round-trip against days of drift; (b) axes —
axis 3 swept explicitly across all tiers (see above); axis 1: rule 11
in both deployments' CLAUDE.md + scout/builder/critic role files of
both; axis 4: index + full text this commit; (c) detector —
REGISTERED via the D-0053 field stream: systematic failure_class=spec
rejections per tier flag DoD-less dispatches (check 13 amended same
commit); a worker starting work on a DoD-less dispatch that later
fails lands in the same stream.

## D-0055
Rule 10(b) is answered by ENUMERATION and enforced at the commit
chokepoint (F-20; operator question "how could you ignore the rule,
and how do we make it unignorable — SYSTEM_PROMPT prose doesn't
work"). Constitutional prose is not self-enforcing anywhere (F-9
generalized to the compliance mechanism itself); what works is the
triple "cheap explicit action + mechanical chokepoint + external
detector". Two parts: (1) FORMAT — the (b) answer is one verdict
line per axis of the CURRENT docs/SIBLING_MAP.md ("ось N: покрыта /
в очередь / н-п <why>"); the axis list is parsed from the map's
headings at every run, never hardcoded — the map grows and shrinks
(D-0048, operator correction) and the gate follows it; recall fails
silently, enumeration fails loudly (skipping an axis now requires
writing an explicit lie). (2) GATE — a commit-msg hook (.githooks/
+ tools/mechanism_gate.py; AO3 twin scripts/mechanism_gate.py reads
the single map from the OS repo, fail-closed if unreachable) rejects
commits touching mechanism paths without the axis block; the block
counts from the commit message plus the staged diff of
docs/DECISIONS_FULL.md ONLY (extraneous staged content must not
close axes — critic finding F-B); the explicit skip line
"оси: не-механизм (<причина>)" counts from the commit MESSAGE only
(a decision text quoting the skip syntax must not self-bypass the
gate — critic finding F-A, confirmed blocker); merge commits pass
(their parts were gated individually — F-C); file prefixes match
exactly, directories by prefix (F-D). AO3 trigger paths: policy,
roles, skills, schemas/, state/rules.yaml; the pipeline's scripts/
are deliberately OUTSIDE the trigger — script changes are covered by
tests and review, and false positives train --no-verify, killing the
gate. History: the gate itself went through the full D-0052..54
discipline as task t-001 — builder-tier work done inline by Lead
(dispatch_skipped with witness), critic dispatched per rule 3
(>100 lines), verdict REWORK with confirmed blocker F-A; fixes
carry regression tests. Honest limits, stated: the hook checks
PRESENCE of the block, not its quality; a "н-п" verdict can be
stamped thoughtlessly; the chat/proposal stage has no hook; bypass
via --no-verify remains possible and is forbidden, not prevented.
Residual detectors: the map's recurrence rule (D-0048), calibration
check 8 (audits answer quality and skip-line honesty), the operator.
Rule 10 answers: (a) cost — six-ish short lines per mechanism commit
(the block), paid by the committer; one hook run per commit
(~100 ms); repaid by turning silent axis omission into visible
refusal; (b) axes, by this decision's own format:
ось 1: покрыта — правило 10 в CLAUDE.md обоих деплоев; хук-твины
  .githooks/ + tools/mechanism_gate.py (OS) и scripts/mechanism_gate.py
  (AO3), новая парная строка внесена в ось 1 карты этим же коммитом;
ось 2: н-п — учёта денег/токенов не касается;
ось 3: покрыта — гейт стоит на ДЕЙСТВИИ (коммит), не на роли: любой
  коммиттер механизмных путей (Lead, builder, деградированный Lead)
  проходит один и тот же турникет;
ось 4: покрыта — DECISIONS индекс + полный текст этим коммитом;
  новая пара «текст правила 10(б) ↔ его enforce-код» зафиксирована
  строкой оси 1;
ось 5: покрыта — тесты гейта: tools/test_mechanism_gate.py (OS,
  40 passed) и scripts/tests/test_mechanism_gate.py (AO3, 249 passed),
  регрессионные тесты на все находки critic;
ось 6: покрыта частично, остаток решением — schemas/ и
  state/rules.yaml в триггере AO3-твина; scripts/ конвейера вне
  триггера сознательно (см. выше), это записанное решение, не пропуск;
(c) detector — REGISTERED: calibration check 8 amended same commit
(hooksPath liveness in both repos, spot-audit of skip lines and of
axis-block presence on the period's mechanism commits); the gate's
own silent-death mode (hook unset/broken) is exactly what the
hooksPath check catches.

## D-0056
Lead tier is verified at both ends and externally (F-21, the twelfth
F-11 case; three operator questions across AO3 sessions 2026-07-08/09).
Silent Lead degradation had no detector: D-0039 entrusted the
`lead_degraded` event to the very party whose downgrade it must
catch, and a restored Lead read the ABSENCE of the event as absence
of the fact (circular; same inference class as "empty output of a
mis-invoked env tool = the object does not exist"). Precedent: an
AO3 session ran a full /qa-loop pass — dispatches, acceptance,
mechanism commits — on Opus (critic tier) with no event; the
restored Lead then denied the window until the operator pointed at
the visible /model command. Neither in-session point suffices alone:
entry fails by self-detection-by-the-degraded (unreliable by
construction), and the ascent may never happen (safety fallback
Fable→Opus that never returns — the session dies degraded). Hence
THREE points: (1) ENTRY — before the FIRST Lead action of a session
(worker dispatch, acceptance, mechanism commit, status change),
compare own model per the last visible signal (session system
prompt; switch command if any) against the Lead tier; below it with
no journal-open window → write `lead_degraded` BEFORE the action.
The trigger is anchored to the action, not to session start: entry
failure is a missing recognized TRIGGER, not a missing signal
(F-20 class). (2) EXIT — a visible ascent is BY ITSELF proof a
window existed, regardless of the journal: same move writes the
retroactive `lead_degraded` (marked retroactive, factual bounds),
performs the D-0044 window acceptance, then `lead_restored`.
(3) EXTERNAL NET — weekly calibration check 5 amended: actual
Lead-session models from transcripts (cc_usage main chains, not
sidechains) vs window coverage by event pairs in both journals; Lead
activity below Fable outside a declared window = silent degradation.
This extends the D-0034/D-0042 model-vs-transcript cross-check from
workers to the Lead itself — the only tier that had no gate (F-20
diagnosis confirmed). Points (1)+(2) landed on AO3 first (CLAUDE.md
"Деградация Lead" п.4 а/б/в; /qa-loop preflight step 0 as the
pipeline's entry turnstile — commits 1efef9f, 642dc30); this commit
ports п.4 into the OS CLAUDE.md degradation section and registers
point (3). Honest limits: both in-session points remain voluntary
self-checks (the entry check is performed by the possibly-degraded
model); what makes the mechanism a mechanism is the external net —
a self-check failure is caught within one calibration period.
Rule 10 answers: (a) cost — one model-vs-tier comparison before the
first Lead action of a session (seconds, paid by the Lead session);
retroactive pair + window acceptance only on an actual ascent; one
sweep line per calibration run (cc_usage query + journal grep), paid
by the calibrator; repaid by closing the only ungated tier — the
precedent's unfixed window silently carried mechanism commits;
(b) axes, by enumeration over the current map:
ось 1: покрыта — п.4 а/б/в теперь в CLAUDE.md ОБОИХ деплоев (AO3:
  коммиты 1efef9f/642dc30; OS: этот коммит); журнальный вокабуляр
  (lead_degraded/lead_restored, ретро-пометка) уже общий; qa-loop
  preflight — AO3-специфичный турникет, у OS конвейерного скилла
  нет (записанное различие, не пропуск);
ось 2: н-п — сверка модели, не денег; калибровочная выборка читает
  cc_usage как есть, ничего в учёт не добавляя;
ось 3: покрыта — механизм закрывает единственную роль без сверки
  (Lead); воркеры уже покрыты чеком 4 (D-0042), судья — D-0031;
ось 4: покрыта — DECISIONS индекс + полный текст этим же коммитом
  (чек 12); наблюдение остаётся в docs/FINDINGS.md F-21 со ссылкой
  на решение (статус-строка обновлена тем же коммитом);
ось 5: н-п — правка политики и протокола, кода нет; счётного
  скрипта у чека 5 нет (как и у остальных чеков — общий queued item
  «deterministic counting script» уже стоит в очереди);
ось 6: покрыта — вход конвейера AO3 несёт шаг 0 preflight (SKILL.md
  qa-loop, коммит 642dc30); прочие звенья цепочки Lead-действий не
  совершают и сверки не требуют;
(c) detector — REGISTERED: calibration check 5 amended same commit
(actual Lead-session models vs window coverage, both journals);
this net is precisely the detector for silent failure of both
in-session points; staleness of the net itself is caught by the
Boot Report's Last Calibration line (D-0047), and check-5 quality
falls under the standing check-8 audit of answer quality.

## D-0057
Scout recon quality is regression-tested by a golden set; agent-prompt
edits carry a regression rule (eval plan stage 1, items 2-3,
operator-approved 2026-07-08; priors: docs/RELATED_WORK.md "Evals").
D-0046 made every scout digest individually acceptable (trail +
spot-checks), but nothing caught TIER-level drift: a scout.md edit or
a tier-model swap could silently degrade recon quality, and the modes
weak models fail quietest — negative claims and invented judgments —
are exactly what per-dispatch acceptance samples least (F-14). The
judge sibling was already fixed this way (D-0031 calibration set,
recalibration on judge swap); this decision extends the same
discipline to the subscription contour's information tier. Mechanism:
PROCESS/SCOUT_GOLDEN_SET.md — 7 fixed recon questions with PINNED
keys (5 point/multi-hop across process, code, policy and table; 1
negative usage-vs-mention trap; 1 judgment-refusal trap), each with a
verify command so the key is re-checked BEFORE every run (CORE-Bench
lesson: fix the eval before blaming the model); dispatched as a plain
recon task without eval marking (working behavior is measured, not a
prepared exam); PASS >= 6/7 with the negative and judgment-refusal
questions mandatory; runs recorded in the set's Runs log. Regression
rule: editing the role file of a tier that HAS a set (today: scout),
or swapping its model, requires a run before the commit, logged in
the same commit. builder deliberately has no set: its output is
verified by artifacts on every task (witness, D-0052) —
execution-based acceptance beats a golden set (Rule #1). critic set
queued (candidate design: review a diff with known seeded defects).
Baseline run t-006 (2026-07-09, haiku, dispatched unmarked): 7/7,
both mandatory questions passed.
Rule 10 answers: (a) cost — one haiku dispatch plus minutes of Lead
key-check and grading per run; triggers are rare (role-file edits,
model swaps, calibration assignment); paid by the Lead session,
repaid by catching recon degradation before it becomes a
false-accept stream (F-14: bad recon surfaces later as builder
failures without attribution);
(b) axes, by enumeration over the current map:
ось 1: в очередь — AO3-порт правила и набора (три общих яруса, на
  следующем касании role-файлов; для 13 QA-агентов конвейера —
  отдельное решение по данным); явная строка в очереди
  CURRENT_CONTEXT этим же коммитом;
ось 2: покрыта — API-контурный собрат уже существует (калибровочный
  сет судьи, D-0031 / JUDGE_CALIBRATION_PROTOCOL: рекалибровка при
  смене модели судьи); этот механизм — его субскрипционный близнец,
  родство зафиксировано в F-14;
ось 3: покрыта перечислением — scout: набор этим коммитом; critic:
  в очередь (кандидатный дизайн в тексте набора); builder: н-п
  (execution-based приёмка witness'ом на каждой задаче сильнее
  набора, Rule #1); судья: уже D-0031; Lead: покрыт
  D-0025/D-0047/D-0056;
ось 4: покрыта — новая пара PROCESS/SCOUT_GOLDEN_SET.md <->
  .claude/agents/scout.md добавлена в карту тем же коммитом; индекс
  DECISIONS + полный текст тем же коммитом (чек 12);
ось 5: н-п — механизм процедурный, тестового кода нет; счётного
  скрипта у чека 14 нет, как и у прочих чеков (общий queued item
  «deterministic counting script»);
ось 6: в очередь — вместе с осью 1 (у qa-конвейера AO3 свои роли и
  свой набор смыслов; порт после решения по 13 агентам);
(c) detector — REGISTERED: calibration check 14 added same commit
(edit-without-run audit via git log over .claude/agents/ of both
deploys; key liveness via verify commands on >=2 questions;
recon-failure growth without an unscheduled run triggers one). The
set's own disappearance is caught by the SIBLING_MAP axis-4 pair
(check 12 liveness sweep); check-14 answer quality falls under the
standing check-8 audit.

## D-0058
Role ≠ tier: a session's authority comes from its ACTUAL model, not
from the policy's addressee (F-22, the thirteenth F-11 case; operator
screenshot of an AO3 session, 2026-07-09). CLAUDE.md auto-loads into
every main-chain session and is addressed to "Lead" — so every model
that read the policy assumed the whole role: a Sonnet coordinator
"accepted" a Sonnet builder-class fix under the critic-skip
concession and a fix-verifier report — same-tier self-certification,
the session-level sibling of F-6 (judge) and F-14 (scout). D-0039
p.2 fenced statuses/gates/DECISIONS off a degraded Lead but not
ACCEPTANCE; D-0056 verifies the tier at entry but no matrix said
what each tier MAY do. This also blocked the operator's planned mode
(coordinate daily from Sonnet, batch Fable runs over an accumulated
Lead queue). Decision: (1) the coordinator ROLE is tier-independent;
FULL Lead = coordinator on the Fable tier, the only one changing
mechanisms, DECISIONS, table statuses, gates. (2) Acceptance only
FROM ABOVE: an `accepted` is legal when the acceptor's tier is
strictly above the worker's, OR the decision carries an
above-tier input (critic verdict), OR the acceptance is explicitly
queued to the full Lead (notes mark). Same/higher tier without such
input = session self-certification. (3) The critic-skip concession
on small diffs belongs ONLY to an acceptor above the worker.
(4) Capability matrix per actual coordinator model in CLAUDE.md of
both deploys ("Роль ≠ ярус"): Fable — unrestricted; Opus — accepts
scout/builder incl. skip concession, critic-class work queued, no
mechanisms/statuses; Sonnet — accepts scout, builder diffs only
with a critic input (no skip), critic-class and Lead-class queued;
below Sonnet coordination is not provided for. (5) The planned
Sonnet-coordinator mode is this same matrix as the NORMAL regime;
degradation (D-0039) is an unplanned entry into it.
Rule 10 answers: (a) cost — zero in the full-Lead regime (Fable is
above every worker; nothing changes); in coordinator mode — a critic
dispatch per builder-class diff (the price of honest acceptance) and
a Lead queue for same/higher-tier work, paid by the operator's
batched Fable sessions; repaid by removing session-level
self-certification (the precedent accepted work on behalf of a tier
the session was not on);
(b) axes, by enumeration over the current map:
ось 1: покрыта — CLAUDE.md («Роль ≠ ярус», деградация п.2, льгота в
  правиле 3) и critic.md обоих деплоев + AO3 qa-loop SKILL.md
  (шаги 0/3) — OS этим коммитом, AO3 коммитом той же сессии;
ось 2: н-п — полномочия, не учёт; детектор читает cc_usage как
  есть, ничего в учёт не добавляя;
ось 3: покрыта перечислением — координатор/Lead: матрица; critic:
  несущая опора приёмки при координаторе ниже Fable (п.9 файла роли
  обоих деплоев); builder/scout: не принимают ничего — без
  изменений (builder.md п.4 уже запрещает самосертификацию
  исполнителя — воркерское зеркало этого же класса); судья: уже
  D-0031 (chief-judge = приёмка сверху);
ось 4: покрыта — DECISIONS индекс + полный текст тем же коммитом
  (чек 12); F-22 в FINDINGS с перекрёстными ссылками; новая ось в
  карту не нужна: правило лежит на существующих осях 1/3/4
  (вертикаль «политика — роли — протокол» уже картирована);
ось 5: н-п — механизм процедурный, кода и тестов нет;
ось 6: покрыта — qa-loop SKILL.md: шаг 0 preflight уже сверяет
  ярус (D-0056), дополняется матрицей полномочий; шаг 3 (accepted
  при result: success) получает условие приёмки сверху; прочие
  звенья цепочки accepted не пишут;
(c) detector — REGISTERED: calibration check 6 amended same commit
(acceptance-from-above audit: acceptor-session tier from cc_usage
vs event agent tier on every accepted; equal/below requires a
critic input or a full-Lead-queue mark in notes); works with check
5 (degradation windows) which catches the windows themselves, and
with the qa-loop preflight step 0 as the pipeline's entry point.

## D-0059
Phase 2 gains a third gated workstream: externalize the task
pipeline — intake, scope, DAG generate, allocate — from the Lead
session's head into explicit artifacts, artifacts before code.
Origin: external advice to the operator (2026-07-09, "for bigger
tasks, add intake/scope and DAG generate/allocate components at the
very start"); operator direction same day. Recon t-008 established
the current state: no code components of this class exist (negative
spot-checked by the Lead's own grep over tools/ and gateway/); all
four functions run manually per CLAUDE.md policy — D-0054 DoD
externalizes scope at DISPATCH granularity only, the task-level DAG
lives nowhere but the Lead session's context and dies at the session
boundary. Full rationale preserved verbatim in docs/TASK_PIPELINE.md
(operator: "so nothing is lost").
Decision: (1) ROADMAP.md Phase 2 gets a "Task pipeline gate" beside
the Router and Context gates, entered on journal evidence only
(scale of multi-dispatch tasks, a confirmed loss across a
dispatch/session boundary, Rule #1 economics). (2) Build-out order
is fixed: task brief (intake+scope) → explicit DAG artifact with
node statuses → allocate column per node from the routing rules →
code/automation last, and only if artifact discipline proves value.
(3) First task when the gate opens is an evaluation of existing
carriers (Claude Code native task tools, a markdown template in
PROCESS/), never a build (D-0030). (4) Authority does not move:
decomposition stays Lead-tier work (D-0037) — what is externalized
is the OUTPUT of the stages, not the right to perform them; flat
delegation is unchanged. (5) This entry plans a workstream and
changes no session behavior — not a mechanism; each artifact/gate
built under it will owe its own Rule 10 answers at its own commit.
Distinct from the Router (D-0029): the Router dispatches an
already-scoped subtask to a model; the allocate stage is its manual
precursor, and their gates are independent.

## D-0060
Parallel-session discipline for the shared journal and working tree
(F-23, fired by the first real parallel-session incident: two
concurrent sessions allocated task_id t-008 to two unrelated tasks,
2026-07-09 — the golden-set run 12:42/12:55 and the task-pipeline
recon 13:20/13:28). The queued Stage-2 rule (owned paths) fired on
its trigger, but the actual collision hit an axis it did not name:
identifier allocation in an append-only shared log — silent, unlike
a path collision which git surfaces itself. Decision: (1) task_id
is allocated by RE-READING the journal tail immediately before
writing the `delegated` event: max existing t-NNN + 1; an id
remembered from earlier in the session is re-derived, never reused.
(2) Parallel dispatches AND parallel sessions declare owned paths
before launch (rule 4 addendum); another session's uncommitted
paths are not touched and not committed. (3) A collision discovered
after the fact is never rewritten (journal append-only): it is
flagged in the notes of the next event of the same task and
recorded in FINDINGS; counting mechanisms treat the duplicated id
as DISTINCT tasks. (4) AO3's log_append.py can enforce id
uniqueness in code — queued (builder, small); the policy line lands
on both deploys now.
Rule 10 answers: (a) cost — one journal-tail re-read per dispatch
(the coordinator re-reads a file it is about to edit anyway — near
zero) plus one owned-paths line per parallel spec; paid by
coordinators, repaid by keeping every journal-derived count (checks
3/13, the queued counting script, calibration evidence) honest;
(b) axes, by enumeration over the current map:
ось 1: покрыта частично — политика (правило 4 + строка в разделе
  журнала) в CLAUDE.md обоих деплоев этим ходом; AO3
  log_append.py code-enforce уникальности — в очередь явной
  строкой (builder, мелкое);
ось 2: н-п — идентификаторы журнала, не учёт денег;
ось 3: н-п — task_id выдаёт координатор; воркеры id не выдают и
  журнал не пишут;
ось 4: покрыта — DECISIONS индекс + полный текст тем же коммитом
  (чек 12); F-23 в FINDINGS; двусмысленная ссылка «recon t-008» в
  docs/TASK_PIPELINE.md уточнена тем же коммитом;
ось 5: н-п — кода нет (enforce уйдёт AO3-стороной из очереди);
ось 6: в очередь — вместе с log_append enforce (конвейер пишет
  журнал только через scripts/log_append.py);
(c) detector — REGISTERED: check 13(д) added same commit (scan for
duplicate t-NNN across unrelated tasks; the known t-008 duplicate
is pinned there as counting as TWO tasks). Path-claim violations
surface as git conflicts / cross-session dirty-tree incidents and
are recorded as findings (the F-23 pattern); the queued counting
script for checks 3/13 inherits the (д) scan.

## D-0061
"Do the next priority task (dispatch independent parts to agents in
the background)" is a COMMAND, not a chat phrase the operator
retypes each session: .claude/skills/next-task/SKILL.md. Origin:
operator request 2026-07-09 after two sessions driven by exactly
this phrase. The skill sequences the existing mechanisms and adds
no rules of its own — CLAUDE.md stays the single source of rules,
the skill orders steps and loses to the policy on any divergence
(same single-owner principle as ROADMAP for phases). Steps: tier
check first (D-0056a) with the D-0058 matrix — the command is
runnable from ANY tier and does not make the session a Lead (a
sub-Fable session coordinates, accepts only below its tier, and
accumulates Lead-class work as explicit queue lines); boot check
(invoking the command IS the operator's work authorization,
satisfying Boot Report protocol rule 4's STOP); priority pick from
CURRENT_CONTEXT (D-0025 current task, else the first executable
queue item; operator-decision items are skipped and reported);
background dispatch with DoD before own work (D-0040/D-0054),
task_id by journal-tail re-read and owned paths (D-0060);
evidence acceptance per tier form and the matrix; rolling commits
(D-0016, D-0055 gate, D-0057 golden-set triggers); final report +
CURRENT_CONTEXT update; no scope beyond the picked task except
explicit on-touch queue items.
Rule 10 answers: (a) cost — the skill file loads only on
invocation (not in the boot path); executing it adds nothing the
policy did not already require; paid by the invoking session,
repaid by removing a retyped operator prompt and by pinning the
step ORDER (tier check before first action — the F-22 failure
mode) into the entry point;
(b) axes, by enumeration over the current map:
ось 1: н-п — записанное различие, не пропуск: вход AO3-конвейера —
  /qa-loop со своим preflight; /next-task — вход OS-репо; порт не
  требуется;
ось 2: н-п — порядок шагов, не учёт;
ось 3: покрыта — шаг 0 ветвит по матрице D-0058: команда исполнима
  с любого яруса, полномочия — от фактической модели;
ось 4: покрыта — DECISIONS индекс + полный текст тем же коммитом
  (чек 12); новая пара SKILL.md <-> CLAUDE.md добавлена в карту тем
  же коммитом (skill не дублирует формулировок правил — против
  расхождения);
ось 5: н-п — кода и тестов нет;
ось 6: н-п — см. ось 1 (/qa-loop уже несёт свой порядок шагов);
(c) detector — named external (registered in the skill text): the
skill only sequences mechanisms that each carry their own detector;
its outputs (journal events, commits, CURRENT_CONTEXT) are audited
by calibration checks 1/3/6/13, and a priority violation is visible
to the NEXT session as a Current-Task-vs-commits mismatch in the
Boot Report (D-0025). Skill-file staleness against policy is caught
by the SIBLING_MAP axis-4 pair (check 12 liveness).