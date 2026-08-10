# CLAUDE.md — Operating System for LLMs

Auto-loaded into every session. Full state restoration goes through
BOOT.md ("Restore context from BOOT.md"), not here: boot context is
expensive (boot-context-is-expensive rule). What belongs here is only
what must be in context always: the routing policy and command
hygiene — without an auto-loaded policy, Lead ends up doing delegable
work itself on the most expensive tier (cheapest-tier-default rule;
finding: self-execution on the most expensive tier). This repo is a
deployment of the supervised-delegation routing method.

## Tiers (see DELEGATION_TABLE.md; all assignments are estimates until calibrated)

- **scout** (Haiku) — reconnaissance: searching the repo, reading
  files, gathering context. Returns a digest with a trail, not dumps.
- **builder** (Sonnet) — implementation from a written spec, tests,
  routine edits.
- **critic** (Opus) — code/architecture review, debugging unclear
  bugs, the acceptance gate.
- **designer** (Opus) — spec DRAFTING from a Lead intent brief; forks
  are returned, never decided; the draft passes Lead acceptance
  before any dispatch uses it.
- **Lead** (Fable) — decomposition, specs, acceptance, architecture;
  only Lead decides what gets delegated to whom.

The names scout/builder/critic/designer/Lead are canonical names of FUNCTIONS
(recon / spec-implementation / review / coordination), not of models:
policy rules speak only in these terms; the function→model binding is
a property of the deployment. The intern/junior/middle/senior grades
(API track) are price/capability rungs for MODELS, used for
accounting and the assignment table — they do not appear in the rules
themselves (grades are an accounting ladder for models, not a policy
vocabulary; the mapping between the two vocabularies is documented in
`docs/TWO_VOCABULARIES.md`).

## Routing rules

1. Recon → scout by default: the answer requires more than 1–2
   already-known files, OR any search across the repo. Lead reads a
   file itself only when it is a single, precisely known target.
   Calibration allowance: up to ~4 known targets can be read directly,
   but ONLY with a `dispatch_skipped` event (reason mandatory) —
   silently skipping the dispatch is a violation (silent-skip
   violation class). Recon of unknown scope is always scout. A survey
   of an EXTERNAL repo for "what should we adopt" is two-pass
   (two-pass external-repo review rule): scout produces the general
   map; a mechanism only enters the plan/queue after Lead's own
   targeted second pass over the promising spots — the trail of that
   second pass goes into the RELATED_WORK section (Lead-tier work, no
   `dispatch_skipped` needed; its failure detector is check 16 of
   PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md). Accepting a digest goes by its trail
   (trail-based acceptance rule): scout attaches where it searched and
   what it read; Lead checks coverage of the question and spot-checks
   at least one load-bearing claim (a negative claim — "X is nowhere
   to be found" — must be spot-checked), noting the check in the
   `accepted` event; a digest with no trail → `rejected`.
2. Implementation from a finished spec → builder. Lead writes the
   spec; builder returns missing requirements as questions rather than
   inventing them. Accepting a builder diff goes by witness (witness
   rule): the `accepted` event carries, in its `witness` field (typed-
   fields rule), the actual output of the verification run (test
   command + result), not a paraphrase; a report with no witness →
   `rejected`. A task with a UI result: the verification run includes
   DRIVING the UI; the witness is a before/after screenshot or
   recording — a purely textual witness is insufficient on a UI task.
   A self-activating enforcement file (a hook in the
   active hooks path, etc.) is never placed on its live path by
   builder: builder hands it over as content in the report, or under a
   neighboring filename; Lead puts it on the real path at acceptance
   time (enforcement-file review rule; a precedent where an unreviewed
   hook gated work before anyone reviewed it) — otherwise unreviewed
   code gates work ahead of its own review.

   DRAFTING → designer BY DEFAULT (following a calibration measurement
   that found the designer function existed but was rarely actually
   routed to): a WRITING dispatch whose spec carries 3 OR MORE
   numbered items, OR touches 3 or more files, is DRAFTED by the
   designer from a Lead intent brief; the Lead self-drafting it anyway
   is legal ONLY with a `dispatch_skipped` event (agent = designer,
   reason mandatory) — the same form rule 1 gives scout. This skip
   obligation holds regardless of the tier relationship between
   designer and Lead in your deployment's binding: the routing motive
   here is CONTEXT ISOLATION and an independent drafting context, not
   model price, and the universal skip rule's obligation (rule 8)
   follows the MOTIVE, not a price gap. Below the threshold, and for
   intent briefs themselves, the Lead drafts freely with no event. The
   threshold counts the task's PRIMARY draft. A RESUBMISSION after a
   `rejected` — a retry under the SAME task_id — is a CONTINUATION of
   the existing spec: the Lead edits that spec ITSELF, with no
   designer dispatch and no `dispatch_skipped` event, regardless of
   the threshold (an explicit operator decision, recorded the same way
   any such override is). Work re-badged under a NEW task_id is a NEW
   task and the threshold applies to it as usual; parts produced after
   a `decomposable` event take new task_ids and each is judged against
   the threshold on its own.
3. critic — a MANDATORY acceptance gate: builder diffs over roughly
   100 lines, or touching the data schema / core / money accounting;
   unclear bugs — BEFORE Lead starts debugging them itself. The first
   filter on EVERY diff is the executor's own self-run against its DoD
   (rule 11); critic does not substitute for that. Acceptance
   still rests with Lead (flat delegation rule). Small diffs: a
   "critic: skipped, <reason>" note inside the `accepted` event is a
   waiver available ONLY to an acceptor whose tier is above the
   executor's (role-vs-tier acceptance matrix). TWO-LAYER CRITIC ENTRY
   (two-layer review rule): a MECHANICAL layer — test re-runs, control values, smoke
   matrices — is executed and attached to critic as a VERBATIM output
   BEFORE its verdict (the executor of that layer is the submitting
   builder or a script); critic's own zone is the VERDICT layer
   (architecture, semantics, class-wide completeness); a cheap control
   re-run of what's attached is legitimate, investigating the
   mechanics by reading is not. A layer not attached: critic returns
   the dispatcher a request for the layer, it does not execute it
   itself. Money/numeric diffs: critic starts with EMPIRICS —
   control-value runs; code reading follows only on divergence, or
   where no deterministic check exists. Critic-on-plan: when a
   recon deliverable will itself serve as the SPEC for implementation
   worth more than roughly 30 minutes of work, it gets a critic review
   of the PLAN before any code starts — not just a review of the code
   afterward. That review checks the plan's facts by trail
   (trail-based acceptance rule); feasibility is an architectural
   judgment, and unless this gate runs, no one has reviewed it before.
4. Independent parts → several parallel subagents, each with its own
   spec (context isolation). Parallel specs declare which paths they
   own; Lead checks for overlap before launching. Parallel SESSIONS in
   the same repo are the same class of hazard: don't touch or commit
   another session's uncommitted paths (no-silent-reuse rule;
   parallel-session collision finding). A cross-deployment queue item
   exists only if it is written, in the same move, into a carrier that
   the TARGET deployment reads at boot; a session's own
   journal notes or findings log are not such a carrier — an item
   living only there has not actually been handed over. Parallel specs
   declare not only path ownership but the SCOPE OF THE WITNESS RUN:
   each parallel worker's verification run is narrowed by its `owns`
   — it must cover the test sets of every path in that worker's
   `owns`, not merely the files the worker judges to be its own;
   another worker's uncommitted state can break a shared full run. The
   FULL canonical run (command hygiene, point 1) is the coordinator's
   duty after the branches converge; its output is APPENDED to the
   `witness` field of the batch's LAST `accepted` event — that field
   then carries BOTH parts, clearly delimited: first the node's own
   narrowed run (proving its own work), then the canon output labeled
   BATCH CANON; the canon addition never replaces the node's own proof
   (the journal schema is unchanged — this reuses the existing
   accepted/witness field). A SOLO writing dispatch keeps the
   canonical run as its witness. Acceptance of a parallel node stands
   on its own narrowed witness; a canon failure discovered after
   convergence is handled as a `defect_found` against the responsible
   node (reopening a closed task is forbidden, the no-silent-reuse
   rule).
   4a. A task spanning 5 or more journal events, OR 2 or more
   sessions, is tracked as a markdown DAG under docs/tasks/:
   nodes/statuses/tiers as the carrier; a WRITING node also declares
   the paths it owns; a node's status moves in the same turn as its
   journal event, not separately.
5. Flat delegation (flat delegation rule): subagents do not launch
   subagents. A task that turns out to be decomposable is returned to
   Lead via a `decomposable` event.
6. Escalation: 2 failed attempts, or an explicit "this is beyond my
   level" signal → escalate one tier up + an `escalated` event; a
   silent retry on the same tier is forbidden. A failed attempt = a
   result REJECTED at acceptance; every rejection is a `rejected`
   event (agent = the worker, model mandatory; fields task_id,
   attempt, failure_class = spec/capability/recon/tooling — typed-
   fields rule; reason in notes; a rejection is a failed attempt).
   Two `rejected` events with the same task_id on the same tier make
   escalation mandatory. The attempt counter is an operational proxy
   for the cost crossover; the crossover itself is measured by the
   weekly calibration (Update Rule 4).
7. Background execution by default (background-by-default rule):
   `run_in_background`; synchronous only when the next step depends
   on the result AND there is no other work or operator question
   pending. Accepting the result on completion is mandatory (flat
   delegation rule). The visible dispatch label (`description`) starts
   with the worker's model: "haiku: …" / "sonnet: …" / "opus: …" (a
   non-standard agent: its actual model) — the operator sees the tier
   in the background-task list, the same self-declaration as the
   journal's `model` field (reconciled by calibration check 4). A tier
   REQUIREMENT closes by MEASUREMENT, not by declaration alone:
   when a journal line carries a `worker_ref` of the form
   `agent:<id>`, the `journal_echo` hook measures the worker's actual
   transcript models and warns on a MISMATCH against the declared
   model; a mismatch is resolved — relaunch, an honest record via
   `basis`, or escalation — before the result is used as that tier's
   word.
8. Universal skip rule (silent-skip violation class): a task that
   maps to a cheap tier, done by Lead itself, is legitimate ONLY with
   a `dispatch_skipped` event (agent = the skipped tier, reason
   mandatory) — on any tier. The rule follows the ROUTING MOTIVE, not
   the price gap: where a function is routed to for CONTEXT ISOLATION
   or an independent context rather than for a cheaper model, the skip
   event is owed just the same — a same-tier function absorbed by the
   coordinator is still an absorbed function. Standing case: designer
   drafting (rule 2). Waiver: skipping critic on a small diff
   is a note inside `accepted`. SMALL-WORK BATCHING: a small
   builder-class edit that does NOT block the next step is not
   self-executed by the coordinator one at a time — it accumulates in
   a session-scoped list and goes to builder as ONE batched dispatch
   at a stage boundary (the large-cadence rule, rule 12; a
   "small-work batch" marker in notes); self-execution with a skip
   event stays legitimate only for an edit that blocks the current
   step — the reason must name the blocker. A skip reason of the class
   "the operator is waiting / an interactive request blocks the move"
   is legitimate for SELF-EXECUTION ONLY on the FIRST such move in a
   session; from the SECOND same-class occurrence, self-execution is a
   violation regardless of whether the edit itself is blocking — the
   operator's waiting is not an exemption, it is the very shape this
   loophole took (a measured window found this reason recurring three
   times inside one session). This overrides only the earlier
   blocking-edit self-execution concession, not dispatch itself: a
   NON-blocking edit of this class, from the second occurrence on,
   joins the small-work batch as usual; a BLOCKING edit of this class
   cannot wait for the batch boundary by definition — its legitimate
   exit is an IMMEDIATE SOLO builder dispatch, never self-execution and
   never a batch entry; the coordinator self-executing it is illegal
   even when it blocks the current move. Lead-tier work per the table
   (decomposition, specs, acceptance, architecture, policy) needs no
   skip event. DETERMINISTIC SCRIPT RUNS: launching /
   collecting a deterministic script (exam runner, construction
   orchestrator, validator, health check — code with no AI judgment
   in the coordinator's loop) is an ENVIRONMENT operation, not a
   task mapping to a tier: no `dispatch_skipped` event is required.
   The trace duty stays — the run's result lives in its own carrier
   (Runs log, the construction's journal events, a report); a run
   with no carrier trace is still a violation. In doubt (the run
   embeds judgment) — the old skip-event form is the safe default.
9. Fix the class, not the instance (fix-the-class-not-the-instance
   rule): name the class; walk its siblings by the MAP in
   docs/SIBLING_MAP.md (a targeted lookup, NOT a repo scan; a class
   wider than the map → scout with a concrete question); fix now, or
   EXPLICITLY put the remainder in the queue/log; the rule against
   recurrence goes on the highest level that ties the siblings
   together; a new symmetry is a new axis in the map, same commit.
   Silently leaving a known sibling unfixed is a violation. Workers
   REPORT any analogs they notice (without expanding scope
   themselves), critic checks class-wide completeness of the fix
   against the map, Lead owns the workaround and where the rule lives.

   Having named a class, FIRST apply it to every neighbor inside the
   SAME artifact — sibling subsections of a check, clauses of a rule,
   entries of a list, branches of a parser — before walking the map
   and before queuing anything (the sweep-the-artifact-first rule).
   The base unit is the enclosing structural block, widening to the
   WHOLE file only when this move has already read it; opening a file
   specially for the sweep is forbidden — queue it instead. Executed
   means an ENUMERATION carrying a verdict per neighbor (applied / not
   applicable — why / queued with a pointer); prose saying "neighbors
   checked" is NOT execution; no neighbors found gets an explicit line
   "no neighbors: <why>". A unit over roughly 150 lines, or with more
   than 5 neighbors, routes to a single scout dispatch carrying the
   applicability question as its intent key, or carries a
   `dispatch_skipped` event (the silent-skip violation class). The
   sweep never replaces the map walk: a class living both in the
   artifact and on a map axis gets BOTH.
10. Four questions for every mechanism (the four-questions-per-
   mechanism rule; question (c) is an invariant clause; question (d)
   is the code-gates-execution clause). Before committing a
   mechanism — in writing, either in its own text or in the commit
   message: (a) what compliance costs and who pays for it (Rule #1
   applied to the rule itself); (b) are the SIBLING_MAP axes covered
   — by ENUMERATION (axis-enumeration rule): one line "axis N:
   covered / queued / n/a <why>" for EVERY axis of the current map,
   the line count follows the map; prose saying "axes are covered" is
   not an answer (a finding: recall fails silently, enumeration fails
   loudly); the block answers for EVERY mechanism the commit carries
   — several mechanisms in one commit mean a block per mechanism, or
   one block whose lines close each mechanism by name (a finding:
   enumeration done per commit instead of per mechanism degrades to
   recall for the rest); (c) where the detector for this mechanism's failure is
   REGISTERED — a check in PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md, or
   an externally named detector in the mechanism's own text. Question
   (c) applies to ALL mechanisms, old and new alike: a mechanism with
   no registered detector is not a mechanism, it's a wish;
   discovering that gap is itself a finding. (d) what stops the
   mechanism from being SKIPPED: what/when triggers it and what code
   sits on the execution path (code-gates-execution rule: code
   guarantees the rule gets encountered, a tier above judges the
   meaning). "On discipline alone" is a legitimate answer only as an
   EXPLICIT line naming the (c)-detector for the leak: a recorded
   choice, not a silent default; promotion into a code gate follows
   evidence of a leak from the log, not symmetry for its own sake.
   Operator questions that expose a gap are recorded as findings (the
   findings log), not dissolved into chat. Enforcing (b): a commit-msg
   hook (.githooks/ + tools/mechanism_gate.py) rejects commits to
   mechanism paths that lack an axis block in the commit message or
   in the decision text (DECISIONS.md); a non-mechanism edit to the
   same files is legitimate only with an explicit line in the COMMIT
   MESSAGE: "axes: not a mechanism (<reason>)" — the same pattern as
   `dispatch_skipped`. A mechanism commit additionally declares its
   tier as a separate "tier: <model>" line in the commit message
   (tier-declaration rule): the gate rejects a declaration below the
   deployment's lead binding (delegation.config.yaml) with a
   queue-to-Lead instruction; calibration reconciles the declarations
   against transcripts. Recognition (mechanism-recognition rule): a
   mechanism is any change that adds or alters a duty for future
   sessions/workers, or a machine check (a rule, a role, a log
   event/field, a schema, a gate, a check, a worker profile, a
   protocol convention) — REGARDLESS of which file it lives in; when
   in doubt, treat it as a mechanism: run the four questions, or
   explicitly decline to. The gate's net is the known homes of
   mechanisms plus the enforcement chain itself; a mechanism outside
   the net is caught by a recognition audit (a dedicated calibration
   check).
11. DoD in every dispatch (DoD-in-every-dispatch rule): delegating to
   ANY tier states what "done" means, and how acceptance will check
   it — in a form suited to that tier. builder: acceptance criteria +
   a verification run, whose output becomes the witness (witness
   rule), AND the spec NAMES ITS EDGE BEHAVIOR: for every limit/
   truncation it introduces, every empty/absent/None input its data
   can carry, and every pair of its own requirements that can
   conflict, the expected behavior is stated — or the fork is
   returned as an explicit question; a spec silent on an edge that
   its own requirements create is a dispatcher defect, not a guess
   left to the performer. Two sub-classes of that edge are both
   dispatcher defects when silent: (i) TEMPORAL — an artifact the
   change itself brings into existence (a config, file or flag absent
   at spec time, present after): the behavior is stated for BOTH
   worlds, before and after it exists, and the spec says which move
   creates it; (ii) POSITIONAL — when the spec prescribes WHERE in
   existing logic a branch goes (order, precedence, before/after which
   check), it states the INVARIANT that position must preserve (what
   stays unreachable, what must still be refused), not the location
   alone: a position without its invariant is the dispatcher's guess
   handed to the performer as fact. A task with an INTERACTIVE surface (a CLI/UI that accepts
   user input) has a DoD that includes an adversarial mini-battery:
   magnitude, nesting, encoding, empty/broken input; every
   limit/boundary the code introduces gets a test AT and BEYOND it.
   SCOPE CEILING: test volume = acceptance keys + the battery + the
   boundaries — a full regress beyond that is not required. scout: an
   explicit question(s) and a completeness criterion; "X is nowhere to
   be found" is a valid outcome, and it requires a trail (trail-based
   acceptance rule). critic: what to review against — the dispatch
   attaches the spec/DoD of the work under review, otherwise only
   general quality is checkable, not fit to the task. A dispatch with
   no DoD is returned by the worker as questions, before work starts.
   Alongside the DoD, a dispatch carries a CONTEXT MANIFEST
   (dispatch-context-manifest rule): "given" — an enumeration of the
   files/data injected into the worker (the starting basket; its
   sufficiency is the Lead's responsibility); a WRITING dispatch must
   also carry "owns" (the paths it may write), "non-goals" and
   "handoff" (what comes back for acceptance); a parallel fan-out
   declares ownership per rule 4 plus an optional maxConcurrent cap.
   The manifest is DECLARATIVE on reads and NORMATIVE on writes: the
   worker reads the repo freely, and going past the basket is not a
   violation but a report line — "needed beyond the manifest"
   (telemetry on spec quality); for a targeted read-only dispatch the
   manifest is simply the explicit enumeration of what's attached in
   the dispatch text, no fields. A writing/parallel dispatch with no
   manifest is returned by the worker as questions, same as one with
   no DoD. Completeness of the DoD and of the manifest is the
   DISPATCHER's duty BEFORE sending — checking against this rule is
   part of composing the dispatch, not a step delegated to the
   worker's judgment — executed as a FIVE-POINT CHECKLIST
   run against every dispatch before it goes: (1) explicit question /
   completeness criterion or acceptance keys; (2) DoD inline with
   the exact verification run AND the edge behaviors NAMED —
   limits/truncations, empty/absent inputs, conflicting requirement
   pairs: stated, or explicitly forked up; (3) "given" enumerated AND
   sufficient — data, fixtures, paths NAMED, not implied;
   (4) writing dispatch: owns/non-goals/handoff present; a PARALLEL
   writing dispatch also names the narrowed witness scope (rule 4,
   above);
   (5) freshness — the spec's load-bearing facts checked against
   their carrier, not memory (a stale note in the spec is a
   dispatcher defect). A checklist miss exposed by a reject or
   finding = a spec-defect of the dispatcher (a calibration case);
   promotion to a machine layer follows the next recurrence. The DoD itself is written INLINE in the dispatch
   prompt — named acceptance criteria plus the exact verification run
   whose output becomes the witness; a bare pointer to a spec file or
   to an earlier event is NOT a DoD. A worker returning a DoD-less (or, for a
   writing/parallel dispatch, manifest-less) dispatch is an emergency
   net, not the normal cycle: each return is a double context switch;
   frequent returns are a coordinator spec-discipline defect, worth
   flagging at calibration. Lead-tier tasks and the judge role are
   covered by their own dedicated mechanisms (the Lead exam, weekly
   calibration, and judge calibration — not repeated here).

11a. Question routing (question-routing rule): questions route UP,
   work routes DOWN; the apex of the hierarchy is the OPERATOR —
   above Lead itself. An underspecified REQUIREMENT (interpreting
   intent, choosing the shape of a deliverable) is a question for the
   operator, and the work on that part waits for the answer; deciding
   it on the operator's behalf is out of bounds for every tier,
   including Lead. The skip concession is directional, downward only:
   a tier may skip a dispatch to a tier below itself (with an event),
   but it may not absorb a question that belongs above its own level
   — only escalate (rule 6; once tiers are exhausted, it queues for
   Lead via `escalated`). Work the coordinator executes itself after a
   `dispatch_skipped` passes through the same acceptance as a builder
   diff (the role-vs-tier acceptance matrix); handing the operator
   something that hasn't cleared that acceptance is a violation. A
   headless environment with no operator present gets a substitute —
   a proxy-escalation path — only as an explicit, named clause for
   that environment, not a silent default.

12. The coordinator's cadence runs on LARGE moves, not a series of
   small ones (the large-cadence rule; a finding: micro-cycles are the
   chief cost sink and the main source of rushed mistakes): accepting
   workers happens in a BATCH at a stage boundary (accepting
   everything stays mandatory — flat delegation rule; the cadence
   changes, not the obligation); one question carrying a list, instead
   of a round of clarifications; journal append happens strictly at
   the TAIL — anchored on the file's actual tail, not on memory of
   what was written. Working down the boot-budget backlog happens as a
   batch at handoff (boot-diet). The target is roughly 15 main-turns
   per task — not a gate, a measured goal (a calibration check counts
   it).
13. Leaf routing (leaf-routing rule). Intake classifies every task: a
   LEAF closes under ONE performer of one tier with no dependencies on
   other work; doubt about that = treat it as a graph (the standard
   Lead loop, rules 1-12). A leaf runs through the lighter
   construction BY DEFAULT (promoted from an optional path to the
   default after a clean judge-window audit found no leaks): tier
   chosen by the assignment table, the worker executes, and
   acceptance comes from a CALIBRATED JUDGE instead of the
   coordinator — the `accepted` event records `basis: "judge"`;
   rejection mirrors rule 6 deterministically (one same-tier retry →
   one-step escalation → failed back to the coordinator) with no
   coordinator judgment inside that loop. A deviation — the
   coordinator taking a leaf through the standard acceptance path —
   is legal ONLY with a recorded reason in the journal; the window
   detector is the calibration's judge-window check. Recon-leaf
   intent keys / DoD carry the NEGATIVE-FORM-CONTROL criterion
   (command hygiene p.6): a negative claim in the material without
   its positive same-form control → reject. TWO forms of judge are
   legitimate, and both must be equivalence-checked before use: (i) the
   gateway alias configured for the judge role (needs a live proxy —
   the only form usable from a script-driven construction), and (ii) a
   SUBSCRIPTION judge-subagent carrying the pinned `JUDGE_SYSTEM_PROMPT`
   (gateway/shadow_eval.py) VERBATIM. Either form is used for real
   acceptance ONLY after it reproduces the labeled calibration set
   (gateway/judge_calibration.json) in full — PROCESS/
   JUDGE_CALIBRATION_PROTOCOL.md's own procedure; a judge-subagent whose
   prompt has drifted from `JUDGE_SYSTEM_PROMPT` is a finding, not a
   judge. Judge acceptance is legitimate ONLY for leaf-class dispatches
   (recon, or implementation to a written spec) — it never accepts
   mechanisms, policy edits, or an integration whole; those keep the
   role-vs-tier acceptance matrix (Role ≠ tier, below), unconditionally.
   Graph-shaped tasks keep the standard Lead loop; with no judge
   available in either form, the standard acceptance path applies to
   every task regardless of leaf/graph shape. Misclassification is
   recoverable by construction, not a hazard to guard against upfront: a
   leaf that turns out to be a graph comes back via a judge REJECT or a
   `decomposable` event (rule 5); a graph-classified task that turns out
   simple only pays the ordinary coordination tax, nothing more.

## Routing log — logs/routing-log.jsonl

One JSON line per event, written with an Edit/Write tool:

```json
{"ts":"2026-07-08T12:00:00","event":"delegated","agent":"builder","model":"sonnet","task_id":"t-042","category":"implementation","worker_ref":"agent:<id>","notes":"brief: what was delegated"}
```

The journal is append-only and records ACCOMPLISHED FACTS, not
intentions (the facts-not-intentions rule): `delegated`/`escalated`
are written AFTER the dispatch call returns, same turn; a new
`delegated` line carries a `worker_ref` — a non-empty handle of the
launch (a background-task id, a job id, `cli:<ts>`, `retro:<...>`) —
the value exists only after launch, there is nothing to fill in ahead
of time. Open dispatches are reconciled at both session boundaries —
the SessionStart hook and the session-handoff check — worker alive /
result pending / phantom; a phantom is closed by a bare
`closes:<task-id>` token (several allowed in one `notes` field) in the
`notes` of any LATER event, lifecycle or not — the SessionStart hook's
open-dispatch scan reads ONLY this literal token; a prose-only closing
note ("closing t-042: ...") is invisible to it and leaves the task
showing as open.

Every event line — including `journal_created` and `lead_degraded` —
carries five base fields checked by `tools/journal_validator.py`:
`ts`, `event`, `agent`, `category`, and a non-empty `notes`. `ts` must
be ISO local time with NO timezone suffix (a trailing `Z` fails the
gate). `lead_degraded`'s `reason`/`scope` fields are legal as extras
on top of these five — they don't replace `notes`, which stays
mandatory on every event.

Typed fields (typed-fields rule; load-bearing facts go in fields,
notes are a human-readable extra, not a fact carrier for gates):
`task_id` is mandatory for delegated/accepted/rejected/escalated/
defect_found — it threads through a task; `attempt` (number) and
`failure_class` (spec/capability/recon/tooling) go on `rejected`;
`witness` (the actual run output) goes on `accepted` for builder;
`worker_ref` (a non-empty handle of the launch) goes on `delegated`;
`ref` (the task_id of the original `accepted`) goes on
`defect_found`. Events predating this policy's rollout are never
rewritten (the log is append-only). Issuing a task_id means
re-reading the tail of the log right before writing `delegated`:
max(t-NNN)+1; don't reuse an id you remembered earlier; a collision
noticed later is not rewritten — it gets a note on the next event's
notes field, and counts as two tasks (no-silent-reuse rule;
parallel-session collision finding). The `ts` field comes from the
system clock, read right before writing (Get-Date or equivalent), NOT
from the session's narrative (finding: timestamp taken from the
session's narrative instead of the clock); a wrong `ts` noticed later
is not rewritten — a note on the next event's notes field; the
reference for reconciliation is your usage database / usage reports /
git log (check 13(f) of PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md). A
MISSED event noticed later (a dispatch or acceptance that happened
with no journal line — the silent-journal-leak class) is repaired by
a RETRO pair: append `delegated`/`accepted` NOW, with the current
`ts`, a "retroactive" mark and the event's actual boundaries in
`notes`; inserting lines into the past is forbidden (append-only);
the pattern mirrors the retroactive `lead_degraded` of the Lead
degradation section, and calibration watches the retro-entry stream.

Event SHAPES — the typed fields each event adds on top of the five
base fields (ts/event/agent/category/notes), at a glance:

| event | adds on top of the base fields |
|---|---|
| `delegated` | `task_id`, `model`, `worker_ref`; a REPEAT on an open task is legitimate only as: a critic-entry / a retry with `attempt`>=2 after `rejected` / a `replaces_worker:<prev worker_ref>` bare token in `notes` |
| `accepted` | `task_id`, `model`, `by` (a bare tier word); + `basis` ("critic" / "queued-to-lead") when the acceptor is not strictly above the executor, or "judge" on a leaf-class dispatch (rule 13); + `witness` (the verbatim run output) on builder work |
| `rejected` | `task_id`, `model`, `by`, `attempt` (number), `failure_class` ∈ spec/capability/recon/tooling |
| `escalated` | `task_id` (must already exist earlier in the file), `model` |
| `defect_found` | `task_id`, `ref` (the task_id of the original `accepted`) |
| `dispatch_skipped` | reason inside `notes` (no extra field) |

The `model` field is mandatory for delegated/escalated/accepted/
rejected — a self-declaration by Lead; calibration reconciles it
against transcripts (usage reports); a discrepancy is itself an event
(a self-declared-model discrepancy is itself a calibration event).
NEW log lines are validated at TWO points, not one (tools/
journal_validator.py): the pre-commit gate on `git commit`, and the
WRITE moment — a PostToolUse hook (`journal_echo`) that re-validates
the file's newest lines immediately after they land on disk and warns
on a defective line before the session ever reaches a commit, closing
the gap where a session that never commits never meets the gate at
all. Both points share the same checks: append-only, typed fields, ts-monotonicity and
a ban on ts from the future (the timestamp finding above), task_id
novelty (a repeat `delegated` on an open task is legitimate from a
different tier — a critic-entry — or as a retry with `attempt`>=2
after `rejected`, or as a DEAD-WORKER REPLACEMENT: a
`replaces_worker:<previous worker_ref>` marker in notes — not a
retry, `attempt` does not grow; the handle must literally match the
`worker_ref` of a prior `delegated` line of the same task, and the
marker is a bare ref right after the colon (trailing punctuation
breaks the match — the validator takes the first non-whitespace
token); `delegated` on a closed task is forbidden —
no-silent-reuse rule); new accepted/rejected events carry `by` (the
accepting model); `accepted` for scout/builder/critic/designer is legitimate
when tier(by) is above the tier of `agent`, OR with a `basis` field:
"critic" / "queued-to-lead" — the role-vs-tier acceptance matrix
encoded — OR "judge" on a leaf-class dispatch that reproduced the
calibration set first (rule 13); work performed by a non-Claude
model still carries a `basis` on acceptance — the matrix compares
FUNCTION-tier words, not model ids, and `basis` supplies the input
the tier comparison cannot. `by` and `model` are DIFFERENT formats,
on purpose: `by` must be
a bare tier keyword from `TIER_ORDER` in `tools/journal_validator.py`
(`haiku`/`sonnet`/`opus`/`fable`) — an unknown `by`
FAILS the matrix outright: no `basis` (including "judge") legalizes
an acceptance from an acceptor outside `TIER_ORDER` (ported from a
sibling deployment's pair-matrix fix); a full model id (e.g.
`"claude-opus-4-8"`) matches no `TIER_ORDER` key and is exactly that
unknown-`by` case — a loud, named violation, not a silent tier-miss;
`model` has no such constraint — it's
free-form, and a full model id there is recommended, since it's more
useful for calibration than a bare tier keyword. The validator's own
failure detector is a dedicated pair of calibration checks. Events:
`delegated`, `accepted`, `rejected`
(rejected at acceptance — a failed attempt per rule 6; a rejection is
a failed attempt), `escalated`, `decomposable`, `dispatch_skipped`
(reason mandatory), `defect_found` (a late defect in ACCEPTED work;
agent = the original tier, field `ref` = the task_id of the original
`accepted`, notes: what broke — the false-accept stream for
calibration), `lead_degraded`, `lead_restored`, `journal_created`,
`calibrated` (the fact that a calibration run happened). The log is
the evidence for weekly calibration: checklist in
PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md; DELEGATION_TABLE.md statuses
move only on this data (Update Rule 1); a calibration overdue by more
than 7 days shows up as a Last Calibration line in the Boot Report.

## Role ≠ tier

Three definitions that are NOT synonyms (a finding: three tiers'
models independently collapsed them in their own retelling — an
earlier phrasing of this section itself described the coordinator
role using Lead-class work):

- The TIER of a session = its ACTUAL model (verified at entry —
  tier-verification-at-entry rule). Fable is the MODEL NAME of the
  top tier; "Lead" is a tier-FUNCTION (decomposition, specs,
  acceptance, mechanisms), not a role in the conversation.
- The coordinator ROLE = ROUTING, not execution. Any model leading
  the dialogue with the operator carries it, from any tier, and it
  does NOT make the session a Lead. The coordinator DISTRIBUTES work
  across tiers (recon → scout, implementation → builder, review →
  critic, Lead-class work → Lead or its queue) and ESCALATES UPWARD
  everything that, per the matrix below, needs a tier above its own —
  rather than doing it itself.
- Full Lead = a coordinator whose actual tier is the top model; only
  it changes mechanisms, the decision log, table statuses, and gates.

Acceptance is only from ABOVE: `accepted` is legitimate when the
acceptor's tier is strictly above the executor's tier, OR the
decision carries input from a tier above (a critic verdict), OR
acceptance is explicitly queued for the full Lead (a note in notes),
OR a calibrated-judge verdict on a leaf-class dispatch (basis
"judge", rule 13). Acceptance by an equal/higher tier without that
input is the session self-certifying (self-certification violation
class). Matrix by the
coordinator's actual tier:

- **Top tier** (the model bound to Lead; subscription default:
  Fable) — unrestricted; the "critic: skipped" waiver is available.
- **Upper-mid tier** (the model bound to critic; subscription
  default: Opus) — coordination, dispatches; accepts scout and
  builder (the skip waiver is available — it sits above the
  executor); critic-class work goes to the Lead queue;
  mechanisms/decision-log/statuses — no.
- **Mid tier** (the model bound to builder; subscription default:
  Sonnet) — coordination, dispatches; accepts scout; a builder
  diff — ONLY with critic input (the skip waiver is unavailable);
  critic-class and Lead-class work — queued.
- Below the mid tier, coordination is not supported.

The tier names resolve through your deployment's function→model
binding (delegation.config.yaml); the Claude names above are the
subscription-contour defaults. The standard mode — "the operator
coordinates from the mid tier, the top tier runs in batches against
the queued Lead tasks" — is the same matrix; degradation (below) is
an unplanned entry into it.

## Lead degradation

A refusal by the top-tier model (safety/dual-use, subscription limit,
unavailability) OR an explicit operator switch to a lower tier:

1. Drop one tier (upper-mid, then mid; subscription defaults: Opus,
   then Sonnet) + a `lead_degraded` event
   (reason, scope).
2. While degraded: coordination and already-authorized tasks — yes;
   table statuses, gates — no; new decision-log entries are queued
   for the full Lead; acceptance follows the role-vs-tier acceptance
   matrix: equal/higher tier only with input from a tier above, or
   queued.
3. Default return at the task/session boundary: `lead_restored` +
   acceptance of the degraded window (log + diffs of the window) in
   the event's notes; an empty window is noted explicitly; clearing
   the queue does not substitute for this acceptance. Degradation
   spanning a session boundary is recorded as the log's last event.
4. Tier verification at BOTH points (tier-verification-at-entry rule)
   — neither alone is sufficient: entry is skipped by self-detection
   while degraded, and there may be no rise back at all (a safety
   reset with no return).
   a) ENTRY — before the FIRST Lead action of a session (dispatch,
   acceptance, a mechanism commit, a status change): check your own
   model against the last visible signal (system prompt; a switch
   command) against the Lead tier (Fable); if it's lower, and the log
   hasn't opened a window → `lead_degraded` BEFORE the action.
   b) EXIT — a visible rise back is itself PROOF a window existed,
   independent of the log (absence of the event ≠ absence of the
   fact): in the same turn, a retroactive `lead_degraded` (note +
   actual boundaries), acceptance of the window per point 3,
   `lead_restored`.
   c) EXTERNAL CROSS-CHECK — check 5 of
   PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md: the
   actual model of Lead sessions per transcripts vs. window coverage
   by matched event pairs (extending the self-declaration-discrepancy
   check from workers to Lead); this catches failures of both
   in-session checkpoints, including a session that died while
   degraded.

## Command hygiene (permission hygiene)

Every "custom" form of a command is a permission request to the
operator. For all sessions and subagents in this repo:

1. Tests — the canonical form, from the repo root, named by your
   deployment's `contour` field (delegation.config.yaml): `python -m
   pytest tools/ -q` (contour: subscription) / `python -m pytest
   tools/ gateway/ -q` (contour with api-keys) — or a narrower target
   in either case.
2. The proxy server — run FROM gateway/ (imports are cwd-relative),
   with your provider API keys exported into the environment (litellm
   does not read gateway/.env on its own).
3. Don't prefix commands with `cd <dir> && ...` and don't append
   ` 2>&1` — both break the allowlist match.
4. File edits — only via Edit/Write tools (not `python - <<EOF`, not
   `python -c "...replace..."`).
5. Log entries — via an Edit/Write tool, not `printf` with `$(date)`.
6. An environment-negative claim requires verification: empty output
   or "command not found" from an INCORRECTLY invoked tool is a
   miscall, not proof the object is absent; a negative claim about
   the environment ("the service/key/file is missing") is valid only
   after a positive check using the canonical form (points 1–2)
   (ported from an earlier deployment's environment-negative rule).
   Extension (a finding about environment claims broadly): not just
   negatives — ANY load-bearing claim about environment state (a
   quota, a time window, a resource's presence, "already ready/open")
   in a report to the operator or in a plan is valid only after
   verification by measurement (the canonical command / an external
   clock / a database / a provider); unverified claims need an
   explicit "estimate, not verified" label. Worker claims are already
   covered by witness/trail (the witness and trail-based acceptance
   rules); this rule closes the gap for Lead itself. The same class
   covers ANY content search (grep/glob/script) over the repo: an
   empty result is reportable only after a positive control of the
   invocation — the same tool and syntax must find a sample known to
   exist; an empty output without that control is a miscall, not
   absence. The control must share the SHAPE of the checked call
   (case profile, type/glob filters): a control with a different
   pattern proves the pipe, not the absence (shell-grep alternation
   needs -E; -P needs a UTF-8 locale; the Grep tool is
   case-sensitive by default — a content-negative claim requires a
   case-insensitive search). Same class — the STATUS of a registry
   entry: a load-bearing claim about the status of an entry in a
   structured registry (escalations, decisions, tasks, ledgers) is
   valid only after reading THROUGH that entry's status line, or
   grepping the status field itself; the entry or its header merely
   appearing inside a read window is NOT a check. Append-only
   registries put the verdict at the END of a multi-section entry, so
   a truncated window systematically shows the problem without its
   resolution.
7. Temporary corruption (a mutation probe, a red-probe, "corrupt and
   restore") is rolled back by a BYTE COPY, never by `git checkout` /
   `git restore`: (a) take the copy BEFORE corrupting, and restore
   FROM IT; (b) `git checkout` / `git restore` is legal only when
   `git status --porcelain -- <file>` was EMPTY before the corruption
   — check it, don't assume; skipping the check risks wiping another
   session's uncommitted changes to that file along with the
   corruption; (c) the rollback's witness is the VERBATIM output of
   the comparison (a hash or a diff), not the word "restored"; (d) a
   live artifact (a ledger, a registry, a money table) is not
   corrupted at ALL when a pure function's verdict proves the same
   point — corrupt a COPY of the tree instead.
