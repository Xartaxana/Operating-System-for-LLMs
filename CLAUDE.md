# CLAUDE.md — Operating System for LLMs

Auto-loaded every session. Full state recovery is BOOT.md
(SessionStart auto-injects it, D-0103; boot context is paid, layers
A+B, D-0038). This file holds only what must ALWAYS be in context:
routing policy and command hygiene (D-0041). Norms live HERE;
rationale and history live in docs/POLICY_FULL.md and
docs/DECISIONS_FULL.md. Permanent behaviour (D-0011): never invent
project state — retrieve it from the repository; the repository
overrides chat. This repo is the reference (dogfooding) deployment.

Size budget: cap 37500 B (breach 37800); amendments = ROWS in a
rule's registry block (the first amendment creates it), never core
paragraphs; rationale → docs/POLICY_FULL.md (axis-4 pair, same
commit). Breach → boot-diet, CLAUDE layer.

## Tiers — functions, not models (D-0062)

| Function | Model here | Work | Deliverable |
|---|---|---|---|
| scout | Sonnet | repo search, file reading, context gathering | digest + Trail, never dumps |
| builder | Sonnet | implementation to a written spec, tests, routine edits | diff report + witness run |
| critic | Opus | code/architecture review, unclear bugs, acceptance gate | verdict + its own trail |
| designer | Opus | spec DRAFTING from a Lead intent brief (forks returned, never decided) | draft spec in the R11 form + fork list |
| Lead | Opus | decomposition, specs, acceptance, architecture, mechanisms | — |

Policy rules speak ONLY these function names; the function→model
binding is a deployment property; it LIVES in delegation.config.yaml
(roles.lead) at the repo root — code gates (mechanism_gate,
journal_validator, session_context) resolve it from there, defaulting
to fable when the file is absent. A RESERVE tier sits ABOVE the Lead
binding (`roles.reserve`) and is summoned only by the operator's word
for the hardest cases (D-0099). Grades (API contour) are accounting
vocabulary, never rule words (ARCHITECTURE.md "Two Vocabularies").

## Routing rules

R1. **Recon → scout BY DEFAULT**: any repo search, or more than 1–2
files known in advance; unknown-volume recon is always scout. The Lead
may point-read a known file; up to ~4 known targets itself ONLY with a
`dispatch_skipped` event (reason mandatory) — a silent skip is a
violation (F-9). A digest is accepted BY TRAIL (where it searched, what
it read) and carries a same-form positive control for every
load-bearing negative — the worker's duty; no trail, or an uncontrolled
negative → `rejected`, in both modes below.

| R1 | when | duty | src |
|---|---|---|---|
| a | survey of an EXTERNAL repo | two-pass: scout delivers the map; a mechanism enters the plan/queue only after the Lead's own targeted second pass, its trail recorded in RELATED_WORK | D-0066 |
| b | verification DEPTH follows the EXAM STATUS of the scout binding, not the model name: the scout binding holds a CURRENT pass of the registered scout exam — current = no rebinding, no scout role-file edit, no exam-set rebuild and no `defect_found` on an accepted digest since that pass | acceptance = trail-coverage check alone; mandatory re-verification of claims and negatives is LIFTED; spot-checks stay legal, optional | D-0102 |
| c | currency voided by any event listed in b | the STRICT form returns until a re-pass: spot-verify at least one load-bearing claim, verifying a negative is mandatory, the check noted in `accepted` | D-0102 |

R2. **Implementation to a ready spec → builder**: the Lead writes the
spec; the builder returns missing requirements as questions, never
invents. Acceptance is by witness — the `accepted` event's `witness`
field carries the VERBATIM output of the verification run (command +
result), not a retelling; a report without a witness → `rejected`. The
designer is a STANDING function: spec DRAFTING from a Lead intent
brief, forks returned and never decided silently; the draft passes the
Lead's acceptance before any dispatch uses it.

| R2 | when | duty | src |
|---|---|---|---|
| a | the task's result is a UI | the run includes DRIVING the UI — the witness is a before/after screenshot/recording; a text-only witness is insufficient | D-0052 |
| b | a self-activating enforcement file (hook on the active hooksPath etc.) | is never placed on the path by its builder: it is delivered as content or under a sibling name, and the Lead places it at acceptance | D-0069 |
| c | a WRITING dispatch whose spec carries ≥3 numbered items, or touches ≥3 files | DRAFTING → designer BY DEFAULT, from a Lead intent brief; the Lead self-drafting it anyway is legal ONLY with a `dispatch_skipped` event (agent = designer, reason mandatory) — the same form R1 gives scout | D-0037 |
| d | designer is NOT a cheaper tier than the Lead — same tier OR above | the obligation in c holds anyway: the routing motive is CONTEXT ISOLATION and an independent drafting context, not model price (R8: motive, not price gap) | D-0037 |
| e | below c's threshold, and for intent briefs themselves | the Lead drafts freely with no event; the threshold counts the task's PRIMARY draft | D-0037 |
| f | a RESUBMISSION after a `rejected` — a retry under the SAME task_id | a CONTINUATION of the existing spec: the Lead edits that spec ITSELF, with no designer dispatch and no `dispatch_skipped` event, regardless of the threshold | D-0037 |
| g | work re-badged under a NEW task_id; parts produced after a `decomposable` | a NEW task each, judged against c's threshold on its own | D-0037 |

R3. **critic is the MANDATORY acceptance gate** for builder diffs
>~100 lines or touching the data schema / core / money accounting,
and for unclear bugs BEFORE the Lead starts debugging itself. The
first filter of EVERY diff is the performer's own DoD self-run (R11)
— the critic does not replace it. TWO-LAYER input: the MECHANICAL
layer (test reruns, control values, smoke matrices) is executed by
the submitting builder or a script and attached VERBATIM before the
verdict; the critic's zone is the VERDICT layer (architecture,
semantics, class completeness). A cheap control re-run of the
attached is legal; investigating mechanics by critic-reading is not.
Layer missing → the critic returns the dispatch with a request, it
does not execute the layer itself. Money/numeric diffs: the critic
starts with EMPIRICS — control-value runs; code reading on divergence
or where no deterministic check exists. CRITIC ON PLAN: a recon
deliverable serving as the SPEC of work >~30 min gets a critic pass
BEFORE code starts — facts verified by trail (D-0046), feasibility as
architectural judgment. Small diffs: "critic: skipped, <reason>"
inside the `accepted` event — a concession ONLY of an acceptor above
the performer (D-0058). Acceptance itself stays with the Lead
(D-0037).

R4. **Independent parts → several parallel workers**, each with its own
spec (context isolation). Parallel specs declare path ownership AND the
SCOPE OF THE WITNESS RUN; the Lead checks overlap before launch. Each
worker's verification run is narrowed by OWNS — it must cover the test
sets of all owned paths in that worker's `owns`, not merely the files
the worker judges to be its own (a named narrow target); another
worker's uncommitted state breaks a shared full run. A SOLO writing
dispatch keeps the canonical run.

| R4 | when | duty | src |
|---|---|---|---|
| a | the branches of a parallel batch have converged | the FULL canonical run (`python -m pytest tools/ gateway/ -q`) is the COORDINATOR's duty; its output is APPENDED to the `witness` field of the batch's LAST `accepted` event, which then carries BOTH parts, clearly delimited: first the node's OWN narrowed run, then the canon output labeled BATCH CANON — the canon addition never replaces the node's own proof | D-0052 |
| b | acceptance of a parallel node | stands on its narrowed witness | D-0052 |
| c | a canon failure discovered after convergence | handled as `defect_found` against the responsible node; reopen is forbidden | D-0060 |
| d | parallel SESSIONS in one repo | the same class: never touch or commit another session's uncommitted paths | D-0060 |
| e | a queue item for ANOTHER deploy | exists only if written IN THE SAME MOVE into the carrier the TARGET deploy reads at boot (OS: CURRENT_CONTEXT.md; AO3: docs/HANDOFF.md); own journal notes / FINDINGS are not a carrier — an item living only there is NOT handed over | D-0082 |
| f | a task of ≥5 journal events OR ≥2 sessions | is carried as a markdown DAG in docs/tasks/ (nodes/statuses/tiers; a WRITING node also declares its owns paths); a node's status moves in the same move as its journal event | D-0080 |

R5. **Flat delegation (D-0037)**: workers never spawn workers. A task
found decomposable returns to the Lead via a `decomposable` event.

R6. **Escalation**: 2 failed attempts or an explicit "not enough
tier" signal → one tier up + an `escalated` event; a silent retry on
the same tier is forbidden. A failed attempt = a result REJECTED at
acceptance; every rejection is a `rejected` event (agent = worker).
Two `rejected` with one task_id on one tier → escalation is
MANDATORY.

R7. **Background dispatch by default (D-0040)**: `run_in_background`;
synchronous only when the next step depends on the result AND there
is no other work or operator question. Acceptance of the result on
completion is mandatory (D-0037). The visible dispatch label
(`description`) starts with the worker's model: "haiku: …" /
"sonnet: …" / "opus: …" (non-standard agent — its actual model); this
is the same self-declaration as the journal's `model` field. A tier
REQUIREMENT closes by MEASUREMENT (D-0083): when a journal line with
`worker_ref agent:<id>` is written, the journal_echo hook measures
the worker's actual transcript models and warns on a MISMATCH with
the declared model; a mismatch is resolved BEFORE the result is used
as that tier's word (relaunch / honest record with basis / escalate).

R8. **Universal skip rule (F-9)**: work mapping to another function,
executed by the coordinator itself, is legal ONLY with a
`dispatch_skipped` event (agent = the skipped function, reason
mandatory) — at ANY tier, except as listed below. The rule follows
the ROUTING MOTIVE, not the price gap: a same-tier function absorbed
by the coordinator is still an absorbed function (standing case:
designer drafting, R2). Lead-tier work per the Tiers table
(decomposition, specs, acceptance, architecture, policy) needs no skip events.

| R8 | when | duty | src |
|---|---|---|---|
| a | a small builder-class edit NOT blocking the next step | never self-executed piecemeal: it accumulates in the session's list and goes to builder as ONE batched dispatch at a stage boundary (marker «батч мелочей» in notes) | D-0081 |
| b | the edit blocks the current move | self-execution with a skip event is legal only for an edit BLOCKING the current move — the reason must name the blockage | D-0081 |
| c | skip reason of the class "the operator is waiting / an interactive request blocks the move", FIRST such move in a session | as in b | D-0081 |
| d | the same class, SECOND and later occurrence in a session, edit NOT blocking | self-execution is a violation regardless of blocking; the edit joins the batch (a) — the operator's waiting is not an exemption, it is the very shape the loophole took | D-0081 |
| e | the same class, SECOND and later occurrence, edit BLOCKING | legal exit is an IMMEDIATE SOLO builder dispatch — never self-execution, never a batch entry; self-executing it is illegal even when it blocks the current move — the override hits the SELF-EXECUTION concession only, not dispatch itself | D-0081 |
| f | launching / collecting a DETERMINISTIC script (exam runner, D-construction orchestrator, validator, health check — code with no AI judgment in the coordinator's loop) | an ENVIRONMENT operation, not a task mapping to a tier: no `dispatch_skipped` event is required | D-0095 |
| g | the same script run | the trace duty stays — the result lives in its own carrier (Runs log, the construction's journal events, a report); a run with no carrier trace is still a violation | D-0095 |
| h | doubt: the run embeds judgment | the skip-event form is the safe default | D-0095 |

R9. **Fix the class, not the instance (D-0043)**: name the class;
walk the siblings VIA docs/SIBLING_MAP.md (point lookup, NOT a repo
scan; class wider than the map → scout with a concrete question); fix
now or EXPLICITLY queue the remainder; place the anti-recurrence rule
at the highest binding level; a new symmetry = a new axis in the map
in the same commit. A silently left known sibling is a violation.
Workers REPORT noticed analogs (without widening scope), the critic
checks the fix's class completeness against the map, the Lead owns
the walk and rule placement.

Having NAMED a class, FIRST apply it to every neighbor inside the
SAME artifact — sibling subsections of the check, clauses of the
rule, entries of the list, branches of the parser — before the map
walk and before the queue (D-0100). The base unit is the enclosing
structural block, widening to the WHOLE file when this move has
already read it; opening a file specially for the sweep is
forbidden — queue it instead. Executed = an ENUMERATION with a
verdict per neighbor (applied / not applicable — why / queued with a
pointer); prose "neighbors checked" is NOT execution; no neighbors —
the explicit line "no neighbors: <why>". A unit over ~150 lines or
over 5 neighbors routes to ONE scout dispatch with the applicability
question as its intent key, or carries a `dispatch_skipped` event
(F-9 class). The sweep never replaces the map walk: a class living
both in the artifact and on an axis gets BOTH.

R10. **Mechanism discipline.** Recognition (D-0065): a mechanism is
ANY edit adding or changing a duty of future sessions/workers or a
machine check — regardless of file; doubt counts as a mechanism: four
questions or an explicit refusal. Four questions (F-11, D-0049,
D-0063/D-0064) — in writing, in the mechanism text or commit message:
(а) what compliance costs and who pays (Rule #1 applied to the rule
itself); (б) SIBLING_MAP axes BY ENUMERATION (D-0055): a line
«ось N: покрыта / в очередь / н-п <why>» per axis of the CURRENT map
per mechanism; (в) where its failure DETECTOR is registered — a
calibration check or a named external one; a mechanism without a
detector is a wish, and finding one is a finding; (г) what stands on
the execution path (D-0063: code guarantees the encounter, an AI tier
above judges the meaning); «held by discipline» is legal only as an
explicit line naming the (в) detector. Enforcement: the commit-msg
gate (.githooks/ + tools/mechanism_gate.py) rejects a mechanism
commit without the axis block and a `tier: <model>` line (D-0072); a
non-mechanism edit of the same paths is legal only with the line
«оси: не-механизм (<reason>)» in the commit MESSAGE. Full procedure:
D-0055/D-0063/D-0064/D-0065/D-0072 (DECISIONS_FULL).

R11. **DoD in every dispatch (D-0054)**: what "done" means and how
acceptance verifies it, in the tier's form, INLINE in the dispatch
prompt — a bare pointer to a spec file or an earlier event is NOT a
DoD. Next to it — the CONTEXT MANIFEST (D-0073): "given" = enumeration
of injected files/data; a writing dispatch adds owns (ABSOLUTE write
paths) / non-goals / handoff. Completeness of both is the DISPATCHER's
duty BEFORE sending (checklist below); silence on an edge its own
requirements create is a dispatcher defect, not the performer's guess.

| R11 | when | duty | src |
|---|---|---|---|
| a | builder | acceptance criteria + the verification run whose output becomes the witness | D-0054 |
| b | the spec sets a limit/truncation, admits an empty/absent/None input its data can carry, or carries pairs of its own requirements that can conflict | for every limit, every such input and every pair of its own requirements that can conflict, the expected behavior is STATED — or the fork is explicitly handed down as a question | D-0054 |
| c | edge sub-class (i) TEMPORAL — an artifact the change itself brings into existence (a config, file or flag absent at spec time, present after) | the behavior is stated for BOTH worlds, before and after it exists, and the spec says which move creates it | D-0054 |
| d | edge sub-class (ii) POSITIONAL — the spec prescribes WHERE in existing logic a branch goes (order, precedence, before/after which check) | it states the INVARIANT that position must preserve (what stays unreachable, what must still be refused), not the location alone: a position without its invariant is the dispatcher's guess handed to the performer as fact | D-0054 |
| e | the task has an INTERACTIVE surface (CLI/UI taking user input) | the DoD adds an adversarial mini-battery — size, nesting, encoding, empty/broken input; every limit/boundary the code introduces gets a test AT and BEYOND it | D-0054 |
| f | test volume under e | SCOPE CEILING: acceptance keys + battery + boundaries; full regress beyond is not required | D-0054 |
| g | scout | explicit question(s) + a completeness criterion ("X is nowhere" is a valid result requiring a trail) | D-0054 |
| h | critic | the spec/DoD of the reviewed work attached | D-0054 |
| i | a parallel fan-out | ownership per R4 + optional maxConcurrent | D-0073 |
| j | the manifest on READS | DECLARATIVE: reading past the basket is a report line, not a violation; a point read-only dispatch just enumerates its basket inline | D-0073 |
| k | the manifest on WRITES | NORMATIVE | D-0073 |
| l | the owns are markdown/config with no test set of their own (DOC-DISPATCH WITNESS) | a deterministic key-presence run IS a legal mechanical layer, but ONLY with three properties: (i) the keys are quoted VERBATIM from the DoD as written BEFORE the run; (ii) the script is committed as a test OR attached in FULL source with the witness; (iii) the run includes a NEGATIVE control (one key deliberately absent → the script reports failure) | D-0052 |
| m | any of l's three properties is missing | the witness is a retelling, not a run (D-0052 class); detector — check 13(л) | D-0052 |
| n | a checklist miss exposed by a reject or finding | a spec-defect of the dispatcher; promotion to a machine layer follows the next recurrence | D-0063 |
| o | a worker returns a DoD-less dispatch (or a writing/parallel one without a manifest) with questions | the emergency net, not the normal cycle: frequent returns = a spec-discipline defect of the coordinator, a calibration case | D-0054 |
| p | edge sub-class (iii) GENERATIVE — the spec's own requirement births an artifact, case or branch absent before it, BEYOND the deliverable the dispatch itself declares | the spec names the birth's CARRIER (file/field/event — where it lives) and its CLASSIFICATION (mechanism path or not; a paired entity — axis 4/registry/detector; the owner), or hands the fork down explicitly as a question; silence is a dispatcher defect, not the performer's guess | D-0054 |
| q | манифест given | исполнен ПОМЕЧЕННОЙ декларацией: инлайн-перечень ИЛИ указатель на персистированную спеку с перечнем (ОДИН переход); без маркера — не манифест; owns строго инлайн | D-0106 |

FIVE-POINT CHECKLIST (D-0096) run against every dispatch before it
goes: (1) explicit question / completeness criterion or acceptance
keys; (2) DoD inline with the exact verification run AND the edge
behaviors NAMED — limits/truncations, empty/absent inputs, conflicting
requirement pairs: stated, or explicitly forked down; (3) "given"
enumerated AND sufficient — data, fixtures, paths NAMED, not implied,
AND the TOOLS OF THE EXECUTING TIER: a fact reachable only through a
tool the performer's role lacks (git history, live process/network
state, anything needing Bash for a Bash-less tier) is put IN THE
BASKET pre-fetched by the dispatcher's own R1/R8(f)-legal route, never
assigned as something the performer must go get — assigning it anyway
is the dispatcher's own spec defect, not a
capability failure of the performer; (4) writing dispatch:
owns/non-goals/handoff present; a PARALLEL writing dispatch also names
the NARROWED witness scope (R4); (5) freshness — the spec's
load-bearing facts checked against their carrier, not memory (a stale
note in the spec is a dispatcher defect; machine layer — the
dispatch_gate given-path warn).

R11a. **Questions route UP, work routes DOWN (D-0077); the USER is
the apex of the hierarchy** (above the Lead). Underspecified
REQUIREMENTS (intent interpretation, choice of result form) are
user-level questions; the affected work stands until answered;
deciding for the user is forbidden at every tier including the Lead.
The skip concession points only DOWN: you may skip a dispatch BELOW
your tier (with the event); a question ABOVE your level cannot be
absorbed — only escalated (R6; tiers exhausted → the Lead queue via
`escalated`). Coordinator work self-executed after `dispatch_skipped`
passes the same acceptance as a builder diff (D-0058 matrix); handing
unaccepted work to the user is a violation. Headless environments
without a user — only via an explicit environment clause with proxy
escalation (exam protocol).

R12. **Coarse cadence — LARGE moves, not series of small ones**:
worker acceptance in bulk at the stage boundary (accepting EVERYTHING
stays mandatory, D-0037 — the cadence changes, not the duty); one
question with a list instead of a clarification loop; journal appends
strictly to the TAIL — the anchor is the file's actual tail, not
memory; boot-budget squeeze batched at handoff. Target ≤15 main moves
per task — a measured goal (exams / calibration check), not a gate.

R13. **Leaf routing (D-0087)**: intake classifies every task — a LEAF
closes under one performer of one allocate-category with no
dependencies; doubt = graph. A leaf runs through the D-construction BY
DEFAULT: category→tier by the ladder, worker executes, acceptance by a
CALIBRATED JUDGE (verdict recorded; `basis: "judge"`), deterministic R6
mirror on reject (one retry same tier → one-step escalation → failed
back to the coordinator); the coordinator stays out of the leaf loop.
Graph tasks keep the standard Lead loop.

| R13 | when | duty | src |
|---|---|---|---|
| a | the coordinator takes a leaf through the standard acceptance path | a deviation: legal ONLY with a recorded reason in the journal; the window detector is check 30 | D-0094 |
| b | recon-leaf intent keys / DoD | carry the NEGATIVE-FORM-CONTROL criterion (command hygiene p.6): a negative claim in the material without its positive same-form control → reject | D-0087 |
| c | which judge is legal | TWO forms: the gateway alias (judge-sonnet, needs a live proxy — the only form for script-driven constructions) and a SUBSCRIPTION judge-subagent carrying the pinned JUDGE_SYSTEM_PROMPT (gateway/shadow_eval.py) VERBATIM; a drifted subagent-judge prompt is a finding, not a judge. With no judge available in either form the standard acceptance path applies | D-0087 |
| d | the dispatch is NOT leaf-class — a mechanism, a policy edit, an integration whole | judge acceptance is illegal: those keep the D-0058 matrix — it is legal ONLY for leaf-class dispatches: recon / implementation to a written spec | D-0087 |
| e | a quality-critical task, on the operator's word | H-mode: a Lead-authored DAG + per-node intent keys incl. adversarial probes + D-machinery on leaves | D-0087 |
| f | the classification was wrong | Misclassification is recoverable by construction: a leaf that was really a graph comes back via judge reject / `decomposable` (R5); a graph-classified simple task only pays the Lead-layer tax | D-0087 |
| g | judge-приёмка листа НЕ заменяет критик-гейт ИНТЕГРАЦИИ | критик при вливании: лист >100 строк; листы одной темы — ВМЕСТЕ; >2 малых одной темы/места последствий — тоже (кумулятив) | D-0110 |

## Journal — logs/routing-log.jsonl

One JSON line per event, written with the Edit/Write tool:

```json
{"ts":"2026-07-08T12:00:00","event":"delegated","agent":"builder","model":"sonnet","task_id":"t-042","category":"implementation","worker_ref":"agent:<id>","notes":"short: what was delegated"}
```

Append-only; records ACCOMPLISHED FACTS, never intentions
(D-0076/F-44). Cadence (D-0079): events accumulate and are written as
a BATCH at the stage boundary — one Edit to the TAIL — but never
later than entering a long wait (background dispatch with no other
work, pre-idle turn end, handoff): facts in session memory die with
it, disk survives; an unwritten journal with live workers is
forbidden. `delegated`/`escalated` — strictly AFTER the dispatch call
returns; a new `delegated` carries a non-empty `worker_ref` (id of
the background task, job id, `cli:<ts>`, `retro:<...>`).

Base fields of EVERY event: ts (ISO, local time, no timezone — read
from the system clock immediately before writing, never from the
session's narrative, F-29), event, agent, category, notes
(non-empty; there is NO separate `reason` field — reasons go inside
notes). NOTES HAS A LENGTH BUDGET: 800 chars for the dispatch cycle, 15000
for `calibrated` (its notes are the declared OWNER of a run's
analysis). Over budget = the note carries what belongs elsewhere —
a load-bearing fact goes to a typed field, an analysis to its own
carrier (task DAG, commit message, report), the note keeps the
pointer. Machine layer: the NOTES LEN warn of journal_echo at write
time (warn, never a block). Event SHAPES — mandatory typed fields on top of the base
(D-0053; load-bearing facts as fields, notes is surplus):

| event | adds on top of base |
|---|---|
| delegated | task_id, model, worker_ref; a REPEAT on an open task only as: critic entry / retry with attempt≥2 after a rejected / `replaces_worker:<prev worker_ref>` bare token in notes |
| accepted | task_id, model, by (TIER WORD: haiku/sonnet/opus/fable); + `basis`: "critic" or "queued-to-lead" when the acceptor is not strictly above, or "judge" on a leaf-class dispatch (R13/D-0087); + `witness` (verbatim run output) on builder work |
| rejected | task_id, model, by, attempt (number), failure_class ∈ spec/capability/recon/tooling — exactly these |
| escalated | task_id (must exist above in the file), model |
| defect_found | task_id, ref (the source accepted's task_id) |
| dispatch_skipped | reason inside notes (no extra field) |

task_id issuance: re-read the journal tail immediately before
writing the delegated — max(t-NNN)+1; never reuse a remembered id.
The past is never rewritten: a later-noticed collision or
wrong ts gets a note in the NEXT event's notes; a missed event is
fixed by a retro pair NOW — current ts, "retroactive" mark, actual
bounds in notes (D-0089); inserting lines into the past is
forbidden. CLOSING an open dispatch: bare token `closes:t-NNN`
(several allowed) in the notes of any LATER event — the SessionStart
hook reads ONLY this token; prose closures are invisible to it; never
write the literal form with a live id in prose. Enforced at TWO
points: the pre-commit validator and the journal_echo write-time warn
(tools/journal_validator.py).

Диаграмма жизненного цикла — docs/POLICY_FULL.md (перенос диетой
2026-08-25); нормы закрытия — текстом ниже.

Closure is reader-specific: journal_validator (D-0060) closes ONLY by
`accepted` — escalated/decomposable/`closes:`-token do NOT close there
(repeat delegated after them stays legal). session_context
`open_dispatches()` is narrower: OPEN only while the LAST lifecycle
event is `delegated`; escalated/decomposable or a later `closes:`
token drop it off the boot list. The readers agree only that
`accepted` closes unconditionally (full text: POLICY_FULL).

Events: `delegated`, `accepted`, `rejected`, `escalated`,
`decomposable`, `dispatch_skipped` (reason mandatory), `defect_found`
(late defect of ACCEPTED work; agent = the original tier),
`lead_degraded`, `lead_restored`, `journal_created`, `calibrated`.
The journal is the evidence of the weekly calibration
(PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md); DELEGATION_TABLE.md
statuses move only on this data (Update Rule 1).

## Role ≠ tier (D-0058, F-22; F-31 — the three definitions below are load-bearing, do not compress)

Three definitions that are NOT synonyms:

- A session's TIER = its ACTUAL model (verified at entry — D-0056).
  Opus is the MODEL NAME of the Lead tier (binding
  delegation.config.yaml, D-0099); Fable is the reserve tier ABOVE
  the binding; "Lead" is the tier-function (decomposition, specs,
  acceptance, mechanisms), not a role in the dialog. THE TWO NAMES
  ARE DATED (2026-08-16), NOT NORMATIVE; the config is the authority
  and wins on divergence (rationale: POLICY_FULL).
- The COORDINATOR role = ROUTING, not execution. Any model leading
  the dialog with the operator carries it, from any tier, and it does
  NOT make the session a Lead. The coordinator DISTRIBUTES work
  across tiers (recon → scout, implementation → builder, review →
  critic, Lead-class → Lead or its queue) and PASSES UP everything
  the matrix below puts above its own tier — instead of doing it
  itself.
- The full Lead = a coordinator whose actual tier is AT or ABOVE the
  Lead binding (Opus; the Fable reserve included); only it changes
  mechanisms, DECISIONS, table statuses and gates.

Acceptance only FROM ABOVE: `accepted` is legal when the acceptor's
tier is strictly above the performer's, OR the decision carries a
higher tier's input (a critic verdict), OR it carries a
calibrated-judge verdict on a leaf-class dispatch (basis "judge",
R13/D-0087), OR acceptance is explicitly queued to the full Lead
(note in notes), OR the acceptor IS the full Lead (tier == the Lead
binding) accepting critic/designer output: the verdict was produced
in an INDEPENDENT context (separate background session), and at the
top of the ladder that independence substitutes for strict model
superiority (D-0099; encoded as the lead-binding branch of
journal_validator — by == binding family accepts agent tiers <=
itself). Equal/higher-tier acceptance without such input = session
self-certification (F-22; class F-6/F-14). The matrix by the
coordinator's ACTUAL tier:

| Coordinator's rung | Accepts | Does not |
|---|---|---|
| `roles.reserve` (above the binding, on operator's word) | everything; "critic: skipped" concession available | — |
| AT `roles.lead` (the binding — full Lead) | everything incl. critic/designer output (independent-context clause, D-0099); "critic: skipped" concession available | — |
| at the `roles.builder` rung | scout; builder diffs ONLY with a critic input (skip concession unavailable) | critic-class and Lead-class → queue |
| below the `roles.builder` rung | no coordination is provided for | — |

Keyed by RUNG, not by model name — pinned names answer the wrong
question after rebinding (register, SIBLING_MAP). Ladder:
scout < builder < critic < lead < reserve. The standing mode
"Sonnet coordinates, Lead runs the queue in batches" is the same
matrix; degradation (below) is an unplanned entry into it.

## Lead degradation (D-0039, D-0042, D-0056)

Triggers: refusal of the Lead-binding model (safety/dual-use,
subscription limit, unavailability) OR the operator explicitly
switching to a lower tier.

While degraded (the window is opened by `lead_degraded` naming cause
and scope): coordination and authorized tasks — yes; table statuses
and gates — no; new DECISIONS → the Lead queue; acceptance per the
Role ≠ tier matrix.
Return is the DEFAULT at the task/session boundary → `lead_restored`
+ acceptance of the window (journal + diffs of ALL repos touched by
the session, D-0044) in the event's notes; an empty window is noted
explicitly.

The tier is verified at BOTH ends (D-0056, F-21) — either alone is
insufficient: (а) ENTRY — before the FIRST Lead action of a session
(dispatch, acceptance, mechanism commit, status change): check your
actual model by the last visible signal against the Lead binding
(`roles.lead`, delegation.config.yaml); lower, with no window opened
in the journal → `lead_degraded` BEFORE the action; a session ABOVE
the binding (`roles.reserve`) is a full Lead with margin — no window
needed, its use is the operator's word (D-0099). (б) EXIT — a visible ascent is by
itself PROOF of a window, regardless of the journal: in the same
move, a retroactive `lead_degraded` (mark + actual bounds), window
acceptance as stated above, `lead_restored`. (в) EXTERNAL NET —
calibration check 5 (transcripts vs window pairs; full text —
protocol). A degradation crossing the session boundary must be the
journal's last event.

## Command hygiene (permission hygiene)

Every "own-form" command = a permission prompt to the operator. For
all sessions and subagents of this repo:

1. Tests — the canonical form from the repo root:
   `python -m pytest tools/ gateway/ -q` (or a narrow target).
2. Proxy server — FROM gateway/ (imports are cwd-relative), with
   GEMINI_API_KEY / GROQ_API_KEY exported (litellm does not read
   gateway/.env itself).
3. Never prefix `cd <dir> && ...`, never append ` 2>&1` — they break
   allowlist matching.
4. File edits — only via the Edit/Write tools (no `python - <<EOF`,
   no `python -c "...replace..."`).

| п.4 | when | duty | src |
|---|---|---|---|
| а | именованный закоммиченный скрипт с приложенным выводом | легален: цель п.4 — ad-hoc мутация, не аудируемый перенос | D-0109 |
| б | payload -c/heredoc — чистый расчёт/чтение | не подпадает, гейт молчит; мутация/непрозрачность — WARN | D-0109 |
5. Journal writes — Edit/Write tool, not printf with `$(date)`.
6. Environment negatives require verification (F-30/F-34): an empty
   output or "command not found" from a MISCALLED tool is a call
   miss, not absence; a negative claim about the environment
   ("service/key/file is absent") is valid only after a positive
   check with the canonical form (pp. 1–2). Extension: ANY
   load-bearing claim about environment state (quota, time window,
   resource presence, "already done/open") in a report or plan is
   valid only after measured verification; unverified — mark
   explicitly "estimate, not verified". Same class — ANY content
   search (grep/glob/script): an empty result is reported only after
   a positive control of the call — the same tool, syntax and FORM
   (case sensitivity, type/glob filters; content negatives only
   case-insensitive) finding a known-present sample; a control with a
   different pattern proves the pipe, not absence; no control →
   emptiness = a call miss. Same class — the STATUS of a registry
   entry: a load-bearing claim about the status of an entry in a
   structured registry (escalations, decisions, tasks, ledgers) is
   valid only after reading THROUGH that entry's status line, or
   grepping the status FIELD itself; the presence of the entry or of
   its header inside a read window is NOT a check. (F-55: the verdict
   sits at the END of an append-only entry — a truncated window shows
   the problem without its resolution).

| п.6 | when | duty | src |
|---|---|---|---|
| а | проектное решение стоит на НЕИЗВЕСТНОМ свойстве среды | сначала ОДИН эксперимент; машинерия вместо замера — лишь при непереносимости замера (порт) или разрушительности опыта | D-0105 |
| б | число замера в норме/отчёте | рядом носитель счёта, либо не писать; сравнение — в одной метрике | D-0107 |
| в | посимвольное утверждение (слэш/регистр/символ) | только по Read носителя; вывод поиска — не основание | D-0108 |

7. **Temporary corruption is rolled back by a BYTE COPY, never by
   `git checkout`** — that idiom wipes ANOTHER session's uncommitted
   changes to the file along with the corruption. For any
   mutation/red probe, at every tier: (а) take a byte copy BEFORE
   corrupting and restore FROM IT; (б) `git checkout`/`git restore` is
   legal only when `git status --porcelain -- <file>` was EMPTY before
   the corruption — check it, never assume; (в) the rollback's witness
   is the VERBATIM output of the comparison (hash or diff), not the
   word "restored"; (г) do NOT corrupt a live artifact at all when a
   function's verdict proves the same thing — corrupt a COPY of the
   tree instead. Detector: calibration check 25 — its transcript scan
   covers this command class.

| п.7 | when | duty | src |
|---|---|---|---|
| д | discarding OWN uncommitted work in a path inside own declared owns, edited in the SAME session | legal; porcelain checked IMMEDIATELY before the rollback (baseline ≠ check); witness = owns declaration + diff BEFORE discard + EMPTY diff after | F-58 |
| е | owns undeclared, path outside owns, or edits not this session's | (б) unchanged: porcelain shows FACT, not AUTHOR — non-empty status outside own owns = a legitimate parallel writer (R4.d), rollback forbidden | F-58 |
