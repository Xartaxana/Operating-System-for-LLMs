<!--
PROVENANCE (install_parity K4b fixture, materialized not live-read):
  source:  D:\Dog\CLAUDE.md at commit ec4e6f0 ("Kit upgrade to v0.8.1
           (public 1d9cbd5 / staff snapshot 1aa9085) with host-branch
           restoration"), 2026-08-13 21:23:49 +0200, full hash
           ec4e6f02950653d3139f340b6d9ae4a147c485ec.
  date materialized: 2026-08-25 (kit v0.9.0 release batch, node C5).
  why:     this is the DOFIX (pre-repair) state of a real upgrade
           incident -- the host-branch-restoration step of that
           upgrade silently reverted ~14 policy blocks in this file
           back to their pre-upgrade text (files landed, the checks
           that reference those rules landed and ran, but the rule
           TEXT was gone -- see D:\Dog\docs\OUTBOUND_TO_KIT.md section
           1 for the five clauses this commit's CLAUDE.md is missing:
           rule 13 leaf routing, rule 2's designer-drafting threshold,
           rule 3's two-layer critic entry, rule 4's witness-run
           scope, rule 8's deterministic-script-runs clause). This
           file reproduces that state so install_parity.py's own
           regression test (test_install_parity.py) can prove the
           tool WOULD have caught it, without a live git-show into
           another repo from the test suite (forbidden by this
           mechanism's own spec, B3).
  content: byte-for-byte the 514 lines of that revision's CLAUDE.md
           (this repo's own vault/AGENTS.md preamble, lines 1-58, plus
           the delivered-but-stale policy block between the BEGIN/END
           markers, lines 59-514) -- untouched below this comment.
-->
# AI-Wiki — Claude Code Instructions

This repo is an AI-maintained knowledge wiki inside an Obsidian vault. You (the LLM) read raw documents from `vault/raw/`, build and maintain interlinked markdown pages in `vault/wiki/`, and save query/lint artifacts to `vault/output/`.

## Layer ownership (strict)

- `vault/raw/` — **read-only**. Never edit or delete files here.
- `vault/wiki/` — you own it. Create, update, link, reorganize freely.
- `vault/output/` — you own it. Query results and lint reports only.

## Schema & workflows

The full schema — page types, frontmatter, workflow steps, linking conventions, tone guide — is defined in `AGENTS.md`. Follow it precisely.

@AGENTS.md

## Slash commands

- `/ingest <file>` — process a new raw source (AGENTS.md §4.1)
- `/query <question>` — answer from the wiki with citations (AGENTS.md §4.2)
- `/lint` — health check against the 10-point checklist (AGENTS.md §4.3)

## Coding guidelines (command-center, scripts)

These apply whenever you write or edit actual code — `command-center/`, the
Python scripts, `.claude/skills/*/scripts/`. They don't apply to wiki content
generation, which follows AGENTS.md instead. Adapted from
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills).

1. **Think before coding** — state assumptions explicitly; if multiple
   interpretations exist, ask instead of picking one silently; push back if a
   simpler approach exists.
2. **Simplicity first** — minimum code that solves the problem; no
   speculative abstractions, flags, or error handling for cases that can't
   happen.
3. **Surgical changes** — touch only what the task requires; don't refactor
   or reformat adjacent code; match existing style.
4. **Goal-driven execution** — for non-trivial changes, verify behavior
   (run the script, hit the endpoint, check the dashboard) rather than
   declaring done once it compiles.

## Environment (Windows host)

This machine is Windows 11; the console codepage is cp1251. Constraints
that have broken runs before — write scripts in a runnable form up front:

- Any script printing non-ASCII (wiki content, transcripts) must run
  with `PYTHONUTF8=1` (or after `chcp 65001`); otherwise long pipelines
  die mid-run with `UnicodeEncodeError` (precedent: transcription
  pipeline crash mid-lecture).
- Never parse locale-dependent CLI output by its human-readable strings
  (precedent: `powercfg` parsing broke on the Russian locale) — use
  machine-readable flags/formats or match locale-independently.
- Deep paths hit Windows MAX_PATH — keep temporary clones and outputs
  in short paths.
- POSIX paths from Git Bash (`/tmp`, `/d/...`) are not valid for
  Node/Python child processes — pass native Windows paths.

<!-- BEGIN supervised-delegation policy (do not hand-edit below this
     line; re-sync by replacing the whole block) -->

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
- **Lead** (Fable) — decomposition, specs, acceptance, architecture;
  only Lead decides what gets delegated to whom.

The names scout/builder/critic/Lead are canonical names of FUNCTIONS
(recon / spec-implementation / review / coordination), not of models:
policy rules speak only in these terms; the function→model binding is
a property of the deployment. The intern/junior/middle/senior grades
(API track) are price/capability rungs for MODELS, used for
accounting and the assignment table — they do not appear in the rules
themselves (grades are an accounting ladder for models, not a policy
vocabulary; the mapping between the two vocabularies is documented
separately in this deployment).

## Routing rules

Scope (D-0003): these rules and the routing-journal duty govern
engineering/system work — code, mechanisms, policy, and recon for
them. Content-production workflows defined by AGENTS.md (ingest §4.1,
query §4.2, lint §4.3, telegram sync/digests, wiki page maintenance)
are EXPLICITLY exempt from the journal duty: content work itself
needs no delegated/dispatch_skipped events. The boundary: the moment
a content session touches code/mechanism/policy paths (tools/,
.claude/, PROCESS/, command-center/, gateway/, root policy files),
the routing rules apply in full to that work. Leak detector for this
boundary: weekly calibration check 1 (its content-exemption clause).

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
   `rejected`. A self-activating enforcement file (a hook in the
   active hooks path, etc.) is never placed on its live path by
   builder: builder hands it over as content in the report, or under a
   neighboring filename; Lead puts it on the real path at acceptance
   time (enforcement-file review rule; a precedent where an unreviewed
   hook gated work before anyone reviewed it) — otherwise unreviewed
   code gates work ahead of its own review.
3. critic — a MANDATORY acceptance gate: builder diffs over roughly
   100 lines, or touching the data schema / core / money accounting;
   unclear bugs — BEFORE Lead starts debugging them itself. Acceptance
   still rests with Lead (flat delegation rule). Small diffs: a
   "critic: skipped, <reason>" note inside the `accepted` event is a
   waiver available ONLY to an acceptor whose tier is above the
   executor's (role-vs-tier acceptance matrix).
4. Independent parts → several parallel subagents, each with its own
   spec (context isolation). Parallel specs declare which paths they
   own; Lead checks for overlap before launching. Parallel SESSIONS in
   the same repo are the same class of hazard: don't touch or commit
   another session's uncommitted paths (no-silent-reuse rule;
   parallel-session collision finding).
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
   delegation rule).
8. Universal skip rule (silent-skip violation class): a task that
   maps to a cheap tier, done by Lead itself, is legitimate ONLY with
   a `dispatch_skipped` event (agent = the skipped tier, reason
   mandatory) — on any tier. Waiver: skipping critic on a small diff
   is a note inside `accepted`. Lead-tier work per the table
   (decomposition, specs, acceptance, architecture, policy) needs no
   skip event. BATCHING (batching rule): a small builder-class edit
   that does NOT block the next step is never executed piecemeal by
   the coordinator itself — it accumulates in the session's own list
   and goes to builder as ONE batched dispatch at a stage boundary
   (marker "batch of small fixes" in notes); self-execution with a
   skip event stays legitimate ONLY for an edit that BLOCKS the
   current move — the reason must name the blockage.
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
   `dispatch_skipped`. Recognition (mechanism-recognition rule): a
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
   rule). scout: an explicit question(s) and a completeness criterion;
   "X is nowhere to be found" is a valid outcome, and it requires a
   trail (trail-based acceptance rule). critic: what to review against
   — the dispatch attaches the spec/DoD of the work under review,
   otherwise only general quality is checkable, not fit to the task. A
   dispatch with no DoD is returned by the worker as questions, before
   work starts. Lead-tier tasks and the judge role are covered by
   their own dedicated mechanisms (the Lead exam, weekly calibration,
   and judge calibration — not repeated here). Next to the DoD sits
   the CONTEXT MANIFEST (context-manifest rule): "given" enumerates
   the injected files/data (the starting basket; its sufficiency is
   Lead's own responsibility); a WRITING dispatch also carries "owns"
   (the paths it may write), "non-goals" (what is explicitly out of
   scope) and "handoff" (what comes back for acceptance); a parallel
   fan-out states ownership per rule 4 plus an optional maxConcurrent
   cap. The manifest is DECLARATIVE on reads — a worker reading past
   its basket is not a violation, only a report line ("needed beyond
   the manifest"), free telemetry on spec quality — and NORMATIVE on
   writes — "owns" is what guards against collisions (the
   no-silent-reuse rule class extended to specs). A point read-only
   dispatch carries its manifest inline, by plainly naming what is
   attached, without the formal fields. A writing or parallel dispatch
   with no manifest is returned by the worker as questions, same as a
   DoD-less one.

11a. Questions travel UP, work travels DOWN; the USER stands at the
   apex of the hierarchy (questions-up-work-down rule), above Lead.
   Underspecified REQUIREMENTS (interpreting intent, choosing the
   result's form) are user-level questions; the affected work stands
   until answered; deciding for the user is off-limits at every tier,
   Lead included. The skip waiver points only DOWNWARD: you may skip a
   dispatch BELOW your own tier (with the event); a question ABOVE
   your level cannot be absorbed — only escalated (rule 6; tiers
   exhausted → the Lead queue via `escalated`). Coordinator work
   self-executed after a `dispatch_skipped` event goes through the
   same acceptance as a builder diff (role-vs-tier acceptance matrix);
   handing unaccepted work to the operator is a violation. A headless
   environment with no user present is handled only via an explicit
   environment clause plus proxy escalation (exam protocol).

12. Coarse cadence — LARGE moves, not a stream of small ones
   (coarse-cadence rule): worker acceptance happens in bulk at the
   stage boundary (accepting EVERYTHING stays mandatory — flat
   delegation rule; the cadence changes, not the duty); one question
   carrying a list replaces a clarification loop; the routing log is
   appended strictly to the TAIL — the anchor is the file's actual
   tail, not memory; boot-budget trims are batched at handoff. A
   target of at most ~15 main moves per task is a measured goal
   (exams / calibration check), not a hard gate.

## Routing log — logs/routing-log.jsonl

One JSON line per event, written with an Edit/Write tool:

```json
{"ts":"2026-07-08T12:00:00","event":"delegated","agent":"builder","model":"sonnet","task_id":"t-042","category":"implementation","notes":"brief: what was delegated"}
```

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
git log (check 13(f) of PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md).

The `model` field is mandatory for delegated/escalated/accepted/
rejected — a self-declaration by Lead; calibration reconciles it
against transcripts (usage reports); a discrepancy is itself an event
(a self-declared-model discrepancy is itself a calibration event).
NEW log lines are validated by a pre-commit gate (tools/
journal_validator.py): append-only, typed fields, ts-monotonicity and
a ban on ts from the future (the timestamp finding above), task_id
novelty (a repeat `delegated` on an open task is legitimate from a
different tier — a critic-entry — or as a retry with `attempt`>=2
after `rejected`; `delegated` on a closed task is forbidden —
no-silent-reuse rule); new accepted/rejected events carry `by` (the
accepting model); `accepted` for scout/builder/critic is legitimate
when tier(by) is above the tier of `agent`, OR with a `basis` field:
"critic" / "queued-to-lead" — the role-vs-tier acceptance matrix
encoded; for non-Claude workers the `basis` field is mandatory on
`by`. The validator's own failure detector is a dedicated pair of
calibration checks. Events: `delegated`, `accepted`, `rejected`
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
acceptance is explicitly queued for the full Lead (a note in notes).
Acceptance by an equal/higher tier without that input is the session
self-certifying (self-certification violation class). Matrix by the
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

1. Tests — the canonical form, from the repo root:
   `python -m pytest tools/ -q` (or a narrower target). This contour
   has no `gateway/` — a `gateway/` target here is a miscall, not a
   broken suite (verified positively 2026-07-26, t-016).
2. The proxy server (api-keys contour ONLY; absent in this
   subscription deployment) — run FROM gateway/ (imports are
   cwd-relative), with your provider API keys exported into the
   environment (litellm does not read gateway/.env on its own).
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
   rules); this rule closes the gap for Lead itself. The same field
   covers ANY content search (grep/glob/script) over the repo: an
   empty result is reportable only after a positive control of the
   invocation — the same tool and syntax must find a sample known to
   exist; an empty output without that control is a miscall, not
   absence (shell-grep alternation needs -E; -P needs a UTF-8
   locale). Known miscall modes in THIS repo, all observed live
   2026-07-25/26 on a Cyrillic corpus: (a) `\b` word boundaries do
   not fire on Cyrillic — the search returns nothing while matches
   exist; (b) shell-grep `-i` does not case-fold Cyrillic here — a
   lookup for a school that exists returned zero, and only the
   positive control exposed it; use the Grep tool or a
   case-exact pattern; (c) searching one language when the data is
   localised — YouTube serves English titles for Russian-audio
   videos, so a Russian-only query reports absent videos that are
   present; (d) searching for a marker in file BODIES when agents
   wrote it in varying formats — take the structural field instead
   (a URL, a path, a frontmatter key). The rule is not the gap;
   compliance is: it was already written here when all four were hit.
7. A repair to a file in the ENFORCEMENT CHAIN is verified against the
   CHECKER THAT WATCHES IT, not only against the symptom it cured. On
   2026-07-25 the fix that unblocked the shell (hook commands rewritten
   to `$CLAUDE_PROJECT_DIR`) was probed correctly — shell alive, gate
   still warning — and accepted; it had silently broken
   tools/wiring_check.py, whose parser knew only the relative form, so
   the SessionStart line printed four "unparsed hook command" warnings
   instead of "WIRING: OK" for a day, until a builder's full-suite run
   on an unrelated task surfaced it. Probing what you fixed is not
   probing what watches it. Machine half: tools/enforcement_probe.py,
   a pre-commit gate that REJECTS a commit touching the chain while
   wiring_check is not OK (fail-closed on purpose; `--no-verify` is the
   visible, deliberate escape). Judgment half: calibration check 19's
   sibling question — was the watcher run at all?

<!-- END supervised-delegation policy -->
