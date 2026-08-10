# Deployment Economy Exam (A/B/C)

A controlled measurement of whether THIS kit's delegation policy pays
off for YOUR deployment: instead of assuming a delegation policy
helps, this exam compares three arms on the same tasks and measures
the gap. Motivating principle: a delegation policy can also actively
underperform, or actively hurt outcomes, relative to no policy at all
-- don't assume the gap, measure it. The exam evaluates the policy AS
A WHOLE; see docs/SIBLING_MAP.md Axis 2 (per-tier exam instruments)
for the separate, narrower calibration exams this economy exam
complements rather than replaces.

## Three arms

The same underlying model, the same harness version, the same tasks
in all three. The polygon is a sandbox (a fresh empty project), NOT
your working repos.

- **A -- clean model:** an empty project; no CLAUDE.md, no agents, no
  special prompt.
- **B -- fresh install of THIS kit:** a fresh install of the kit as
  shipped (policy + agents + journal). The install's own boot cost is
  honestly counted into this arm's price -- boot context is not free.
- **C -- "a good prompt" without infrastructure:** a canonical prompt,
  verbatim: "Using a workflow approach, dispatch Sonnet and Opus
  subagents wherever possible." Recorded consequence: Haiku is
  deliberately NOT named in the prompt -- C represents a strong user
  without this kit's policy; the gap in cheap recon (the Haiku tier)
  is one of the measured differences between B and C. Purpose of this
  arm: isolate the contribution of INFRASTRUCTURE from the
  contribution of a simple reminder. C ~= B means the kit is carrying
  dead weight; B > C is the policy proven against the strongest cheap
  alternative.

## Tasks

3-5 tasks of different kinds, EXECUTABLE (not vignettes). Key
requirement of form: the wording is DELIBERATELY UNDERSPECIFIED --
like a real user request ("write me a calculator"), leaving a share
of the architectural decisions to the arm under test. A fully
specified task is builder-class work ("even the mid tier can do it")
-- it doesn't exercise the coordination layer (decomposition,
architecture choice, specs to workers, acceptance). Underspecification
is exactly what forces an arm to show HOW it turns intent into a plan
and to whom it hands out the parts.

Composition: at least one "product from scratch" task (underspecified,
architectural), one recon of a third-party repository, one fix/review
of existing code; variety matters more than count.

Requirements:

1. NOT from your own repositories and not already solved in them
   (contamination).
2. Acceptance keys are written IN ADVANCE, at the level of INTENT
   (what the result must be able to do, how you'll check it), NOT an
   implementation spec -- the arm under test must build the spec
   itself; keys are never handed to the arms (pre-registration
   discipline). A key that encodes ONE interpretation of an
   underspecified intent is itself a decision made on the user's
   behalf; such keys are marked "interpretation: disputes go to the
   operator" at pin time. A clarifying question back to the user, from
   an arm, is recorded in the verdict as a POSITIVE (an arm that never
   asks and always decides for the user is a finding, not a neutral
   fact).
3. The set is pinned before the first run; swapping a task afterward
   is a line in the Runs log with a reason.

## Metrics (by decreasing weight)

1. **Price per ACCEPTED task** -- accounted prices, cache-aware, ALL
   attempts and retries included. A task that was not accepted earns
   the arm no points, however much it saved.
2. **Share of delegated work** -- sidechain spend / total spend (from
   your usage tracker; measured on every arm, doesn't need a journal).
3. **Escalations/retries before acceptance.** Mandatory result-table
   COLUMNS: (a) rejects/retries per arm (arms with a journal: count of
   rejected/attempt events; arms without one: "n/a" -- honestly, their
   internal retries are invisible, and that invisibility is itself a
   measured difference of the infrastructure); (b) turns by model,
   main/side split (usage-tracker GROUP BY model, is_sidechain over
   the arm's sandboxes) -- raw material for "coordinator moves vs.
   worker moves" without further arithmetic; (c) for journal-less arms
   -- WORKER LAUNCHES (distinct agent ids), with the caveat that
   launches != retries (a planned fan-out multiplies agents without
   retrying; a retried continuation of one agent does not) -- resolving
   whether a journal-less arm's launches were retries needs transcript
   forensics, on request.
4. **Speed:** task wall-clock = min..max ts across ALL of the
   sandbox's usage rows (main + sidechains); one method for every run,
   cross-run deltas only by that one method. WINDOW PARALLELISM is
   MEASURED (other projects' rows inside the window), never declared
   -- a self-reported "clean window" is not evidence. Idle-time
   attribution: only EXTERNAL idle time with measured parallel load is
   subtracted; delays from the arm's own orchestration are part of its
   own time.
5. For B specifically: journal discipline was actually followed
   (dispatch/acceptance events on record) -- otherwise this arm
   measured something other than your policy.
6. Quality beyond binary acceptance: the verdict records qualitative
   differences between arms (tests/review/safety/trail) even when
   both sides are "accepted" -- price without quality doesn't mean
   anything.
   6a. **QUALITY TABLE.** Quality is a VECTOR of five axes in [0,1],
   weights below (adjust for your own priorities and record the
   change with a date):
   - A correctness (an adversarial battery, pinned before the run,
     identical across every arm) x1
   - B completeness against INTENT (an intent checklist, independent
     of delivery form) x1
   - C test quality (mutation kill rate; run on trigger, see below) x1
   - D persistence of evidence (acceptance is reproducible from files;
     deployment-neutral, any carrier counts) x0.5
   - E auditability (the reasoning behind decisions is recoverable
     from files by ANY carrier, not just this kit's own format) x0.5

   Composite scalar = weighted sum / sum of weights of the APPLICABLE
   axes (axis C doesn't apply to a pure-recon task -- it drops out of
   the denominator). F = $ per weighted point -- a derived summary of
   Rule #1, not an axis of its own.

   Discipline: battery A and checklist B are pinned BEFORE the run;
   axes A/D are scored deterministically by the runner/collector; a
   full axis-C mutation run and a quality panel for axis B run on
   TRIGGER (the cheap axes are close, or the task is large); subjective
   axes are scored BLIND (de-identified arms). If you use a judge panel
   for axis B/E scoring, it follows the same equivalence discipline as
   PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (reproduce a labeled
   calibration set before it scores anything for real).

   GRANULARITY: score PER TASK (an axis n/a to a given task drops from
   that task's own denominator); F is also per-task (task price / task
   scalar); an arm's scalar is the mean of its tasks' scalars.

Acceptance is by DoD, per your own routing policy; disputed verdicts
go to the operator. Instrument: your usage-tracking tool (per-session);
arm sessions live in sandbox projects, tagged in the Runs log.

**REPORT FORMAT:** the default output of a run's analysis is a
PER-TASK matrix (row = arm x task), columns: quality-table scalar for
the task | F ($ per weighted point for the task) | task price | clean
time (start..end cells from run_log, external idle time subtracted per
the attribution rule above) | tier path (main model + sidechains with
turn counts) | missed defects (surviving mutations, delivery defects,
unclosed keys -- named). Arm aggregates (total, $/accepted, composite
scalar) go in a row AFTER the matrix, never instead of it. The Runs
log below keeps the AGGREGATE row only (its table format is
unchanged); the per-task matrix lives in the run's own analysis notes
or grading logs alongside it.

**RESULTS REGISTRY:** keep a living results file (e.g.
docs/EXAM_RESULTS.xlsx, or an equivalent spreadsheet/table you
control) with per-task rows once you have per-task data, and arm
totals by formula. Every run's analysis adds its rows to this
registry in the SAME move that adds its Runs log line below -- a run
logged here without a matching registry row is a process gap worth
catching at your own calibration cadence.

**UI acceptance:** a task whose result is a UI is accepted only by
DRIVING the UI (before/after screenshots or a recording as the
witness) -- reading the code statically is not enough; a visual
defect can pass code-level acceptance and only be caught by actually
looking at the screen.

## Measurement honesty

- A single run is noisy: at minimum, record the spread and label
  conclusions "single run"; the norm is a median of 2-3 repeats per
  task ("never trust one run").
- Arms run close together in time (one model/harness version).
- Arm order on a task varies (no "favourite last arm" bias).
- Accounting honesty: exam sessions live in sandboxes OUTSIDE your
  working repos (attributed by project in the usage tracker); the
  exam window is marked explicitly in the notes of your next regular
  calibration -- synthetic load is not disguised as real work and
  does not silently skew your regular trend checks. Arm B's spend on
  any API-billed contour it delegates onto is counted from that
  contour's own accounting, at accounted prices; there is no separate
  "API arm" -- on an API contour there is no coordinator carrier to
  build one around, and building one purely for the exam violates
  Rule #1.

## Reference task set (example only -- not shipped with this kit)

The task set below shows the SHAPE this exam's tasks typically take,
and matches the two built-in fixture-copy branches the runner's
prepare() function supports (needs=click, needs=todo -- see
tools/exam_runner.py). It is NOT shipped as ready-to-run content:
build your own three (or more) tasks from your own non-contaminated
sources per the requirements above, using this as a template.

- **T1 "Calculator"** (architectural, from scratch). Verbatim prompt:
  "Write me a calculator." Acceptance keys: (1) it works and is
  demonstrated (witness class: a run/tests); (2) control expressions:
  2+2*2=6 (precedence), parentheses, division by zero handled
  sensibly, negatives, fractions; (3) architectural choices (CLI/GUI/
  web form; parser vs. eval, and safety if eval) are NAMED and
  justified; (4) tests, or an explicit demonstration of correctness.
- **T2 "Recon of a third-party repo"** (needs=click in the manifest --
  the runner git-clones whatever repo you point src.click_git at; it
  does not have to be the click library specifically, any well-known
  third-party CLI/library repo works). Example prompt shape: "There's
  a clone of \<library\> in this directory. Work out how its \<some
  non-trivial subsystem\> works, and produce a report with a plan for
  adding \<some feature\>: what to change, where, what the risks are."
  Keys: (1) real carriers are named (concrete files/functions/line
  ranges); (2) the subsystem's behavior is described correctly; (3)
  the plan is buildable, files are named; (4) the report carries a
  trail (where it looked). Acceptance is checked against the live
  clone.
- **T3 "Fix existing code"** (needs=todo in the manifest -- the
  runner copies whatever files you put under src.fixture_dir; this
  kit does NOT ship that fixture directory, per the
  CRITIC_EXAM/SCOUT_GOLDEN_SET pattern below -- populate it yourself
  before running prepare() on a needs=todo task, or prepare() refuses
  with a named error naming the missing/empty path). Example prompt
  shape: a small existing program with a real, reproducible bug class
  (e.g. "users report X breaks after Y; fix it, and make sure this
  CLASS of bug doesn't come back"). Keys: (1) the bug is named
  correctly (root cause, not symptom); (2) the fix addresses the
  class (a real invariant, not a patch over one instance); (3) "class
  closed": a regression test/invariant; (4) the rest of the program's
  existing behavior is unbroken (a run proves it).

## Headless escalation proxy

An automated run (a runner, headless sessions) removes the arm's
channel to "ask the user" -- a user-level question dies into stdout
with no one to answer it. The standard environment-conditions line
below goes as a SUFFIX to every arm that has a questioning
infrastructure (typically B; whether A/C get it too is a pinning
decision for your own task set), verbatim:

> Session-conditions note: the user is unavailable and cannot answer.
> If a question comes up that needs the user's word (interpreting
> intent, choosing the shape of a result), do NOT decide it yourself
> and do not leave it unanswered: escalate it by dispatching a
> subagent on your top tier (label "top-tier: verdict ...") and treat
> its answer as the proxy user's word. Then carry the work through to
> completion.

A proxy verdict is NOT the user's word: it is marked as such in the
cell's verdict; the proxy model = your deployment's Lead-tier binding.
This is a PROSTHESIS for exam conditions, not a policy rule (in
production, questions go to a live user -- see your routing policy's
question-routing rule). HARDENING: a proxy verdict is valid only when
the answering model is actually MEASURED (a tier-echo check inside
the sandbox; at analysis time, reconciled against your usage tracker
by agent id); a substituted proxy (claimed one tier, measured
another) is an analysis finding, and the grader is responsible for
checking every claimed proxy escalation against the tracker.

## Cadence and trigger

TWO EXAM CLASSES:

- **SMALL exam** -- tasks of the reference-set class (~10-minute
  tasks), mid-tier coordinator, the runner. Goes into EVERY regular
  calibration cycle -- it accumulates STATISTICS over time (price/
  speed medians, reject variance; this is how "a single run is noisy"
  gets cured by accumulation, not by repeating runs in one sitting).
- **LARGE exam** -- multi-session, a larger reference set. EXPENSIVE:
  run periodically, not every calibration cycle, no more than once
  per release. Triggers: a release snapshot of the kit (the same
  deployment regression, but for the whole policy), a major policy
  change, or an explicit operator/owner decision.

Detector: your regular calibration protocol should carry a check for
"a release with no LARGE-exam line here in the window", and,
separately, a check that the SMALL exam ran on schedule (both are
checklist items you own -- see PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md
for the pattern this kit uses for other checks). Results feed a
controlled-comparison writeup and your own delegation-table
calibration, if you keep one (Update Rule 1 in DELEGATION_TABLE.md).

EXECUTION AND MODEL: the standard run is AUTOMATED (tools/
exam_runner.py, a run-manifest as a per-run artifact you keep under
docs/tasks/ or an equivalent location); the session coordinator model
and the kit version under test are both recorded in the Runs log line
below. Pin the kit version explicitly for a run whose purpose is
isolating one variable (e.g. comparing two coordinator models on the
SAME kit version); by default the kit under test is your current
branch at run time (rebuilding the polygon from your own kit-sync
mechanism, if you have one, is part of run prep).

CRITIC_EXAM/SCOUT_GOLDEN_SET instances are NOT shipped with this kit
-- they are generated on onboarding (see docs/SIBLING_MAP.md Axis 2);
critic_exam_N_dispatch.md files are not shipped either. The same
non-shipping pattern applies to this exam's own reference-set
fixtures (T3's todo-fixture files above): build them once, locally,
and keep them out of version control if they carry no reusable value
beyond your own runs.

## Runs log

| Date | Release/occasion | Model | Tasks | A: $/accepted | B: $/accepted | C: $/accepted | Delegated share A/B/C | Min/task A/B/C | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

Fill one row per run (small or large); keep the AGGREGATE-only shape
here (per-task matrices live in the run's own analysis notes/grading
logs, per the REPORT FORMAT rule above). An empty table (just the
header row) is the correct state for a kit that has not run this exam
yet -- see tools/exam_runner.py's collect() for how a fresh polygon
with zero runs is handled (a clear message, not a traceback, and no
degenerate all-zero dossier).
