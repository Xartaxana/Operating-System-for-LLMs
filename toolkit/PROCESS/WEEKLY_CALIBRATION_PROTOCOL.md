# Weekly Calibration Protocol

An executable checklist for the weekly calibration run. Loaded only
for the duration of the run, not at boot. Without a single canonical
checklist, checks tend to scatter across separate decision entries
covering rules 1–10, and the calibrator ends up re-deriving them each
time; this file is their canonical home. A new mechanism that
promises "calibration will catch X" is obligated to add a check here
in the same commit — otherwise the promise is empty (a mechanism with
no registered detector is not a mechanism, it's a wish).

Input data: logs/routing-log.jsonl (across every deployment you run),
usage records (cc_usage) via tools/usage_report.py, the git history
for the period, and diffs to DECISIONS.md.

## Checklist (mechanism → violation → how to check)

1. **Rules 1/2/8 — silent self-exclusion.** Main sessions in the
   usage records with a large volume of reads/edits, for which the
   same period shows neither a `delegated` nor a `dispatch_skipped`
   event. Source: usage report + journal.
   (b) WITHIN-SESSION RECURRENCE of the "first move free" self-execution
   waiver (rule 8): `dispatch_skipped` events of ONE session are
   grouped by reason CLASS in ts order; the SECOND and later event of
   the SAME class in the SAME session is a VIOLATION IN ITS OWN RIGHT,
   independent of whether that reason class has also crossed any
   across-window repeat threshold elsewhere (a separate signal, not
   replaced or overridden by this one). Reference class: "the operator
   is waiting / an interactive request blocks the move". SESSION
   BOUNDARY: the transcript is the final arbiter; a cheap first pass
   is self-declaration — every `dispatch_skipped` event from the
   second one of its class onward in a session is obligated to carry a
   repeat marker in notes ("repeat of class", "second occurrence" — any
   explicit line), making the violation visible by grep without
   touching the transcript. Both layers are checked: the transcript
   scan is the final arbiter, the notes marker is the cheap first pass;
   a second-or-later same-class event with no marker is itself a
   violation (self-declaration failed). An empty window (no skip
   events, or no class repeated within one session) is noted
   explicitly — "no within-session recurrence".
   (c) DISPATCHER THRESHOLD OF THE DESIGNER (the detector for rule 2's
   designer-drafting threshold clause): every WRITING `delegated` of
   the window whose spec carries 3 OR MORE numbered items, OR touches
   3 or more files (counted from the dispatch's `owns` line and from
   the diff of the accepted work), is obligated to carry EITHER a
   paired `delegated(designer)` before it, OR a
   `dispatch_skipped(agent=designer)` with a named reason. Neither of
   the two = a silent absorption of the function by the coordinator —
   the same violation class as self-reading instead of dispatching
   scout. A measure alongside, for TREND not violation: the count of
   designer dispatches in the window against the count of writing
   dispatches above the threshold. Track this ratio over time: a rule
   can exist on paper and still see zero real use until routing
   default forces it — a rising share is the rule's own goal; no rise
   while the rule is live is a leak, a finding.
   (d) THE "RESUBMISSION = CONTINUATION OF THE SPEC" EXCEPTION (rule
   2's own carve-out) — detector: a `delegated` with `attempt`>=2
   under the SAME `task_id` after a `rejected` is a continuation of an
   already-written spec; a designer dispatch and a
   `dispatch_skipped(agent=designer)` are NOT required for it, and
   threshold (c) above does not project onto it. LEAKAGE OF THE
   EXCEPTION: re-badging the continuation under a NEW `task_id` — a
   window task whose subject and `owns` set match a just-rejected task
   (adjacent `ts`, the same path owner), with no paired
   `delegated(designer)` and no `dispatch_skipped(agent=designer)` —
   is a leak of the exception (the norm bypassed by swapping the
   task_id). REVERSE LEAKAGE: a skip event whose reason names
   "resubmission" as its class means the norm is misunderstood —
   either it really was a new task (a designer dispatch was owed and
   the event was filed wrong), or the event itself is superfluous (the
   exception already frees a resubmission with no events at all);
   either case is a finding. An empty window (no rejected-then-
   resubmitted tasks under threshold (c), no re-badging under an
   adjacent task_id, no skip events of class "resubmission") is noted
   explicitly — "no resubmissions".
2. **Rule 3 — critic on large diffs.** Commits in the period with
   over roughly 100 changed lines, accepted with no
   `delegated(critic)` and no "critic: skipped, <reason>" note in the
   accepting `accepted` event. Source: `git log --stat` + journal.
3. **Rule 6 / the escalation rule.** Two `rejected` events for the
   same task at the same tier with no subsequent `escalated` = a
   violation. An `escalated` with no `rejected` trail = a question
   about the self-declaration. This is checked mechanically: events
   for one task are linked by `task_id`, attempts by the `attempt`
   field; an event from the task_id-mandatory set with no `task_id`
   is a violation in its own right (the typed-fields rule).
4. **The self-declared-model discrepancy check.** The `model` field
   on delegated/escalated/accepted/rejected against the actual
   execution models in the usage records; a discrepancy is itself a
   calibration event.
5. **Degradation.** Every `lead_restored` carries, in its notes, a
   review of the window (what was reviewed, the verdict; an empty
   window is noted explicitly). A `lead_degraded` with no matching
   `lead_restored` by the session boundary — cross-check against the
   journal's last event. Cross-check the actual models of Lead
   sessions in the period (main chains in the usage records, NOT
   sidechains) against window coverage by matched
   lead_degraded/lead_restored pairs: Lead-tier activity on a model
   below the top tier, outside a declared window, is silent
   degradation — a failure of both in-session checkpoints (this
   extends check 4 from workers to Lead itself; retroactive pairs are
   found via a note in notes).
6. **Acceptance.** Every completed `delegated` has a matching
   `accepted` or `rejected`. `accepted` for scout dispatches carries a
   note of a targeted spot-check (negative claims — mandatory).
   Acceptance from above: for every `accepted`, cross-check the tier
   of the accepting session (usage records, main chain at the time of
   the event) against the tier of `agent` — strictly above: fine;
   equal or below: notes must carry input from a tier above (a critic
   verdict) or a "queued for the full Lead" note, otherwise it's a
   violation (the session self-certifying). The "critic: skipped"
   waiver is legitimate only for an acceptor above the executor —
   read this together with check 5 (degradation windows).
   Environment-negative claims: negative claims ABOUT THE ENVIRONMENT
   in reports/verdicts of the window (no service/command/file) are
   valid only with a positive check using the canonical form (command
   hygiene, point 6).
7. **Journal vs. transcripts, both directions.** A sidechain in the
   usage records with no matching `delegated` event = an
   undocumented dispatch; a `delegated` with no matching sidechain =
   a phantom event.
8. **The four-questions-per-mechanism rule.** New DECISIONS.md
   entries for the period contain answers to (a)/(b)/(c)/(d), and the
   (c)-answer is REGISTERED: a check in this protocol added in the
   same commit, or an explicit external detector named in the
   decision's own text. An unregistered detector is a wish dressed as
   a mechanism — write it up as a finding. The (d)-answer names the
   enforcement layer: what triggers the mechanism and what code sits
   on the execution path, or an explicit "on discipline alone" line
   with a named leak detector; a missing (d)-line, or a
   discipline-only answer with no detector, is a finding. A
   recognition audit: commits for the period, across every repo you
   run this in, are scanned for mechanism-shaped edits with no
   four-questions block and no matching decision entry (a duty or
   machine check added outside DECISIONS.md is an "unrecognized
   mechanism"); the verdict is a judgment call for the calibrating
   Lead — the gate's net only supplies candidates; anything found is
   a finding, plus a retroactive four-questions writeup. The
   (b)-answer is an axis-by-axis ENUMERATION against the current
   SIBLING_MAP (prose saying "axes are covered" is not an answer);
   gate liveness = `git config core.hooksPath` pointing at
   `.githooks` in every repo you run this in; mechanism-shaped commits
   for the period are spot-checked for the axis block (the only way
   around the gate is `--no-verify` or an explicit waiver line);
   "axes: not a mechanism" lines for the period are audited for
   honesty — a waiver used on a substantive mechanism is a violation.
   Tier declarations: `tier:` lines on mechanism commits for the
   period are reconciled against the sessions' actual models per your
   usage records/transcripts (same reference as check 5) — a lead-tier
   declaration written by a below-lead session is a violation (the
   recognized-then-did-it-anyway class: the gate forces the
   declaration, this check judges its truth); "axes: not a mechanism"
   lines are also audited as a potential bypass of the tier
   requirement (a substantive mechanism relabeled to avoid declaring
   the tier).
9. **SIBLING_MAP — class-wide completeness.** Commits that close a
   finding name the axes it touches; "new axis for SIBLING_MAP" lines
   noted anywhere in your logs get folded into the map.
   (b) SWEEP INSIDE THE ARTIFACT (the sweep-the-artifact-first rule,
   CLAUDE.md rule 9). Every window finding that names a CLASS (a
   findings log, critic verdicts, journal event notes) carries an
   enumeration of its own artifact's neighbors with a verdict on each,
   or an explicit line "no neighbors: <why>". Either form missing is a
   window finding in its own right. A cheap first pass: grep for the
   enumeration marker, with a positive control of the same form; the
   final arbiter is reading the entry itself. FORMALITY DETECTOR: an
   enumeration where EVERY neighbor gets "not applicable" with no
   statement of what distinguishes that neighbor from the found
   instance is a rubber stamp, and a finding in its own right. An
   empty window (no class-named findings) is noted explicitly.
10. **Growth of live files.** Line counts of the boot-path files (the
    files BOOT.md's boot sequence reads, plus CLAUDE.md and
    CURRENT_CONTEXT.md), plus docs/SIBLING_MAP.md (the map is
    supposed to stay small); compare against the previous run (the
    numbers go in the `calibrated` event's notes). Monotonic growth of
    a live file = a violation (closed material not being archived).
11. **Rule #1 applied to the routing machinery itself.** Routing
    overhead measured from data, not estimates: the share of Lead-tier
    tokens spent on journal/acceptance/spot-checks/specs, against the
    cost of the delegated work itself (usage records: main session vs.
    sidechains for the period). If the mechanism's overhead is
    systematically comparable to the work it routes, that's evidence
    for simplifying the mechanism — by a decision, not by quietly
    ignoring it. Also here — the synchronous-dispatch check: window
    dispatches run synchronously are spot-checked against a
    justification in the delegating event's notes (rule 7: synchronous
    only when the next step depends on the result AND no other work is
    pending); a sync dispatch with no justification is a finding.
    Also here — the size of the SessionStart hook's output (Rule #1
    applied to "reality piped into context"): measure
    `echo '{}' | python tools/session_context.py` with a byte/line
    count, both numbers going in the `calibrated` event's notes next
    to the check-10 counts; monotonic growth run over run with no
    decision behind it is evidence for simplification — the same
    class as the overhead check above.
12. **SIBLING_MAP liveness.** Every concrete path named in the map
    exists; the rules/mechanisms it names are still live. A dead path
    is a violation of the map's own same-commit-maintenance rule.
    Repeats in the period (a defect of an already-fixed class
    recurring outside the map's listed spots) get written up as
    findings about the map itself, and the axis gets corrected. If
    you keep decisions as an index plus a full-text companion file,
    the count of entries in each must match; if you keep a single
    DECISIONS.md, this half of the check doesn't apply.
13. **Evidence-based acceptance (both directions), typed fields.**
    (a) Every `accepted` for a builder dispatch carries a `witness`
    field — the actual output of the verification run (command +
    result); `accepted` for builder work with no witness is a
    violation. (b) `defect_found` events reference the task_id of the
    original `accepted` via the `ref` field; the false-accept rate by
    tier (defect_found / accepted for the window) is computed and
    written into the `calibrated` event's notes; a systematic
    false-accept rate for a tier is evidence for moving that tier's
    table status DOWN (Update Rule 1). (c) Every `rejected` carries a
    `failure_class` (spec / capability / recon / tooling); a missing
    class is a violation (check together with check 3). Counts for
    checks 3 and 13 are produced by `tools/calibration_counts.py`: the
    script prints CANDIDATES, and the verdict is left to the
    calibrating Lead. The counting script's own failure detector:
    tests in the canonical suite run; a baseline cross-check (the
    numbers from your first manual count are recorded in a
    `calibrated` event's notes and reproduced by the script on later
    runs); on every run, Lead spot-checks 1–2 counts against the
    journal by hand; schema drift is caught by a test that keeps the
    counting script's constants in sync with the journal validator.
    (d) A systematic `failure_class=spec` for a tier signals
    dispatches with no DoD; check the Lead's recent specs for
    acceptance criteria plus a verification run AND for the context
    manifest (a writing dispatch with no "given"/"owns" is a leak of
    the dispatch-context-manifest rule); a systematic
    `failure_class=recon` on builder signals an insufficient "given"
    basket; "needed beyond the manifest" report lines are direct
    telemetry of the same (piling up → the Lead's baskets are
    systematically thin).
    (e) Task_id integrity: no duplicate task_ids between unrelated
    tasks, across every journal you run. A known-duplicate id
    recorded in the journal counts as TWO tasks in every check-3/13
    count from then on (note it on the following event; don't rewrite
    history).
    (f) Timestamp honesty: spot-check event timestamps for the window
    against an external clock (a request database / usage records /
    git log — sources written by code, not narrative); an
    out-of-order or non-monotonic timestamp within a session is a
    violation (the `ts` field is read from the clock right before
    writing, never from the session's own narrative). A known past
    timestamp error stays un-rewritten; for any timeline count that
    spans it, take the real times from the correcting event's notes.
    (g) SessionStart hook liveness: the hook fails open (if it breaks,
    it warns and exits 0, so sessions keep running without "reality
    piped in"). Check: 1–2 transcripts in the window show a
    "NOW: ... (local system clock)" line at session start; its
    absence means the hook is broken or unregistered — a violation.
    The same check catches a failed startup preflight: a new
    `rejected`/`failure_class=tooling` from a provider quota error
    while `tools/preflight_quota.py` exists means either something
    bypassed the script, or the script's own math has a leak — work
    out which. The hook's MODEL line is a harness-supplied
    declaration, not a measurement, and its wording says so: liveness
    also includes a "declared by harness, not measured" marker on
    that line — the marker disappearing after a hook edit is a
    regression. Reconciling the actual tier against reality is check
    5's job; this subcheck only verifies the declaration's wording
    stays honest.
    (h) traffic_kind honesty: a spot-scan of the window's requests for
    the signature of an unmarked generator — a multi-alias batch in a
    single tick (several models sharing a millisecond-precision ts)
    AND/OR tiny token counts (total < ~100) carrying
    traffic_kind='real'. Found → identify the generator, add a
    self-tag, and correct the mistagged rows loudly by an explicit
    Lead decision (rows named + rationale); a silent after-the-fact
    correction with no commit/journal record is itself a violation of
    this check.
    (i) Phantom dispatches: an open `delegated` window (the task_id's
    last lifecycle event is `delegated`, with no matching
    accepted/rejected/escalated) that outlives the session that opened
    it is a phantom candidate — reconcile its `worker_ref` against
    transcripts / the task list (did the worker actually exist?); a
    `delegated` line with no `worker_ref` once the field is
    validator-enforced is itself a violation (the validator should
    have blocked it — something bypassed the commit-time gate);
    spot-check 1–2 window `worker_ref` values against a real worker (a
    sidechain transcript, a job log).
    (j) NARROWED WITNESS SCOPE OF A PARALLEL NODE (rule 4). For every
    group of window `delegated` entries that ran CONCURRENTLY
    (overlapping delegated…accepted windows with different
    `worker_ref`s), check whether the DoD required TWO OR MORE workers
    of the group to each run the SAME full canonical run
    (command hygiene, point 1). Requiring that is a spec defect of the
    DISPATCHER, even when the runs happened not to conflict that time.
    DATA SIGNATURE: the `witness` field of two or more concurrent
    builder acceptances carries the output of the FULL canonical run
    instead of a narrowed target. Exactly ONE full canonical run is
    legitimate per window — the coordinator's, AFTER the branches
    converge — identified by a "BATCH CANON" label in the `witness` of
    the batch's LAST `accepted` event (rule 4 names this the carrier);
    a second or later full run in the `witness` of the same group is a
    violation. SECOND SIGNATURE: a parallel node's `witness` NOT
    covering the test sets of every path in its OWN `owns` (the rule
    says "narrowed BY OWNS", not "narrowed to whatever the node
    touched") is the same class of spec defect, even when the missed
    path wasn't touched by the node's diff. An empty window (no
    concurrent `delegated` groups) is noted explicitly — "no
    concurrent groups".
14. **A golden set for recon, and a regression rule for prompt
    edits.** (a) Git log for the window on `.claude/agents/*.md`:
    every edit to a tier's role file that has an exam set (scout —
    PROCESS/SCOUT_GOLDEN_SET.md; critic — PROCESS/CRITIC_EXAM.md,
    both generated at onboarding), and every change to its `model:`
    frontmatter, is accompanied by a Runs-log line in that set's
    file in the same commit; an edit with no run is a violation. (b) Key
    liveness: run the verify commands for at least 2 questions in the
    set; a stale key is a bug in the eval itself — fix it BEFORE
    drawing any conclusion about scout degrading. (c) A rise in
    `failure_class=recon` for the window (check together with check
    3), with no out-of-cycle set run, means one should be scheduled.
    (d) Edits to tier role files with NO exam set (builder — by
    design: execution-based acceptance covers every task) get a note
    in the `calibrated` event. (e) A fabrication guard for any exam or
    entrance run that goes through a non-Claude harness: every such
    run in the window is checked by `tools/pi_run_guard.py` and
    carries a guard verdict (a Runs-log line / journal event) BEFORE
    it's graded against the key; an accepted or graded run with no
    guard line is a leak of the discipline-only trigger (evidence for
    promoting it into a code gate). Guard liveness: a known-bad replay
    fed to the guard must come back REJECTED.
15. **Repeated critic findings -> codification, with mandatory
    attribution.** (i) Base: verdicts of the window are walked for a
    finding CLASS that recurs 2 or more times (including findings that
    never escalated all the way to a formal defect) -- a recurring
    class is codified: a line in a spec/builder template, a new axis
    in the symmetry map, or a rule (the fix-the-class-not-the-instance
    rule, extended here to review findings, not only code defects); a
    repeat of an ALREADY-codified class is itself a finding -- the
    codification leaked. (ii) MANDATORY ATTRIBUTION: every verdict of
    the window carrying a rework/blocker note, and every `rejected`
    event, is attributed to its source -- a spec defect of the
    DISPATCHER (a gap/contradiction in the spec, an unnamed item in
    the given basket) | an error of the performer | external. (iii)
    Cluster the attributed causes; record the cluster COUNT in the
    `calibrated` event's notes. (iv) Landing: a dispatcher-side cause
    recurring 2 or more times in the SAME run is landed as a line/
    refinement of the five-point pre-dispatch checklist (rule 11's own
    checklist; this deployment keeps no separate checklist file — a
    recorded choice against a diverging duplicate) -- or an explicit
    line `not codified: <why>`. (v) The measurable goal: a class that
    has landed in the checklist produces no repeat rework in the NEXT
    window; a repeat is itself a codification leak. (vi) This check's
    OWN failure detector: a window with rework/reject verdicts but no
    cluster count in the `calibrated` event's notes is a leak of this
    very norm.

    Edge behavior (named, not left to the runner's guess): an EMPTY
    window (no rework/reject verdicts at all) records an explicit line
    `no rework/reject verdicts in the window` rather than silence. An
    AMBIGUOUS source (more than one plausible cause) is attributed to
    the class `unattributed`, with the ambiguity itself named in
    notes. A verdict whose cause chains through BOTH the dispatcher and
    the performer (e.g. a vague spec that the performer also
    misread) is attributed to the EARLIEST cause in the chain (the
    dispatcher) as primary, with the second cause recorded alongside,
    not silently dropped. At the landing THRESHOLD (exactly 2
    repeats): landing into the checklist is mandatory, same as any
    higher count; at 1 repeat: record the class, do not land it yet
    (landing needs the SECOND occurrence to confirm a pattern, not a
    single data point). Landing a class into the pre-dispatch
    checklist is itself an edit of CLAUDE.md -- Lead-tier work, named
    explicitly, not delegated.

    Acceptance of this check's own output is TEXTUAL (a witness run
    does not cover a judgment call like class/attribution) -- a named,
    accepted limit of this check, not an oversight.
16. **Two-pass external recon.** New RELATED_WORK entries for the
    period (and queue entries referencing an external survey): does
    each one name Lead's own second-pass trail — which files of the
    external repo Lead read itself, beyond the scout's digest? A
    section or plan resting on the digest alone, with no second-pass
    trail, is a finding; mechanisms drawn from such a plan freeze in
    the queue until the second pass happens.
17. Reserved for deployment-specific checks (register yours here —
    see the mechanism rule: every mechanism registers its failure
    detector). Example candidates for this slot: an integration gate
    your own host layers on top of the shipped ones (a CI check, a
    deploy-time smoke test), or a threshold rule for your own workers
    that this protocol has no generic check for (a domain-specific
    limit, a local escalation trigger) — register the check here
    rather than leaving that mechanism's detector-registration
    question unanswered.
18. **Economic trend (Rule #1 applied to the whole system) — "are we
    actually saving, and which way is the trend going."** Every run:
    `python tools/savings_report.py --until <end of window>` (full
    list-price API rates from usage_report.py, cache discounts
    counted, no batch pricing). In the `calibrated` event's notes,
    record four numbers against the previous data point: (a) $/day for
    the routed window; (b) gross savings versus the delegation
    counterfactual (in $ and %: sidechains as they actually ran,
    priced against that same token profile at top-tier rates); (c)
    cost per accepted unit of delegated work (sidechain actuals /
    accepted count across your journals for the window — check 13
    supplies the count); (d) API-track accounting: a rollup by
    traffic_kind plus the real-traffic share. Your first run records
    the baseline — note the method caveats alongside it (a baseline
    taken while still building mechanisms is censored, and the
    coordination premium isn't separable from non-delegable Lead
    work); read the trend only with those caveats until you've
    accumulated weeks without active mechanism-building. This check's
    own failure detector: missing economic numbers in a `calibrated`
    event's notes are visible to the next run and to the operator (the
    same class as a partial count silently passing as complete); the
    script's own failure mode is caught by tests in the canonical
    suite run.

19. **Policy-as-code gates.** Posture: this check compares
    `.claude/settings.json` against its OWN state AT RUN TIME — every
    SessionStart/PreToolUse/PostToolUse/SubagentStop/Stop entry, the
    full list of `command` strings — not against a fixed list in this
    protocol, which is a dated reference snapshot and goes stale the
    moment a hook is added or removed; a mismatch between the
    reference snapshot below and the file's actual content is itself a
    finding, even when the added/missing hook isn't touched by any
    other sub-check here. REFERENCE SNAPSHOT (navigation only, not the
    source of truth): twelve command hooks — session_context
    (SessionStart); dispatch_gate/critic_snapshot/owns_gate (PreToolUse
    Task|Agent); hygiene_gate (PreToolUse Bash|PowerShell);
    claim_control_gate (PreToolUse Edit|Write); dod_track/journal_echo
    (PostToolUse Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell);
    search_control_gate (PostToolUse Bash|PowerShell|Grep|Glob|Read);
    negative_lint (PostToolUse Task|Agent); dod_gate (SubagentStop);
    main_gate (Stop) — a missing entry against the actual file is
    itself a finding (a rule that used to be enforced by discipline
    alone has silently reverted to that).
    Liveness: with live dispatches in the window, `.claude/dod_track/`
    is non-empty for at least one session, and any accumulated
    `gate_log` entries are non-empty; every gate silent while
    dispatches keep happening is a failure of the posture check above,
    not a clean bill of health -- verify the hooks actually ran before
    concluding "no blocks were needed". Blocks: spot-check 1-2
    `gate_log` entries (`blocked` / `skipped_after_2_blocks`) against
    the session's actual edits/runs for the window; a logged block
    with no matching fact in the track, or a block that shouldn't have
    fired given the track's own contents, is a finding about the gate
    itself, not about the session it blocked.

    PER-GATE ACCOUNTING: this posture check's duty is, for EVERY hook
    this posture names, to establish whether it is named ANYWHERE in
    this protocol as the subject of a failure/liveness check — a grep
    of the hook's name across the whole file, with a positive control
    of the same call form on every zero result. A name-match falls
    into one of three categories, and only the middle one counts:
    (1) MERELY MENTIONED — the name appears in prose, in a reference
    snapshot, or in a rollup that lists every hook by name (a rollup
    like that cannot serve as its own positive control) — does NOT
    count; (2) NAMED AS THE SUBJECT of its own failure/liveness check
    — a subcheck here prescribes what is verified for THIS gate and
    what counts as its failure, OR a mechanism resolves unambiguously
    to this gate from the run's own data (e.g. a `gate_log` event
    whose `gate` field names it, even where the surrounding prose
    never spells the name out) — counts, but FULL credit requires the
    prescribed check to be able to detect the gate's SILENCE (firing
    zero times), not only its wrong firing: a check that only
    cross-references EXISTING records ("no false blocks found") cannot
    tell "no violations happened" apart from "the gate is dead and
    writes nothing", and earns PARTIAL credit only; (3) NAMED AS A
    TOOL FOR SOMEONE ELSE'S CHECK — the gate is cited only because
    another check borrows something from it (a file, a line, an
    anchor) to verify a DIFFERENT subject — does NOT count. Category
    (2) is re-derived at every run by re-reading the relevant
    subchecks fresh, never from a cached summary of a past run (a
    summary is navigation, not a source of truth, and goes stale the
    moment the underlying subchecks change). A hook covered nowhere —
    neither the full nor the partial form of (2), nor the excusing
    form (3) — is itself a finding.

    (a) PROBE OF GATE-CODE LIVENESS: run
    `python tools/hook_liveness_probe.py` from the repo root and
    attach its output VERBATIM. The probe feeds each command hook of
    `.claude/settings.json` — including claim_control_gate,
    search_control_gate and negative_lint — a deliberately triggering
    stdin payload inside an isolated temporary tree, and asserts the
    expected trace: a printed reply carrying an anchor and a declared
    exit code, or a file artifact for gates that are silent by design.
    The run itself is the INDEPENDENT fact-trigger: the trace is
    obligated, so a gate's silence is distinguishable from "no
    violations happened" — closing exactly the gap PER-GATE ACCOUNTING
    names above for a category-(2) check that only cross-references
    existing records. Any verdict other than OK (DEAD / MISMATCH /
    CRASH / HUNG / MISSING / CASE-MISSING / STALE-CASE /
    LIVE-STATE-TOUCHED / SETTINGS-UNREADABLE) is a posture finding
    addressed BY GATE NAME. No attached output = this check is NOT
    done. KNOWN BENIGN FLAKE: a LIVE-STATE-TOUCHED verdict on the
    CURRENT session's own ledger file during a long run can be a
    timing coincidence with that same session's own PostToolUse hook
    writing — rerun; a PERSISTENT repeat is a genuine finding. LIMIT,
    STATED EXPLICITLY: the probe proves CODE liveness, not WIRING
    liveness (registration in `.claude/settings.json`, the matcher,
    `core.hooksPath`) — wiring stays with the Posture paragraph above
    and `tools/wiring_check.py`; crediting Posture through this probe
    is forbidden.

Numbering note: checks 20 and 21 below are this deployment's own
sequence, continuing straight on from 19 (no numbering gap) -- they are
the local equivalents of a source deployment's checks 30 and 31, ported
adapted to this file's own numbering rather than reproduced under
matching numbers, since this protocol's own sequence has never mirrored
a source protocol number-for-number (see checks 15/17, reserved
placeholders unique to this file). The correspondence is recorded here,
once, rather than in every cross-reference below.

Checks 23-29 continue the same pattern (source checks ported under this
file's own continuous numbering, not reproduced under matching
numbers): source check 0 -> 23; source check 20 -> 24; source check 21
-> 25; source check 24 -> 26; source check 25 -> 27; source check 29 ->
28; source check 32 -> 29 (recast from the adopting/receiving side to
the REDISTRIBUTOR side -- see check 29's own applicability clause; the
receiving side is check 22, already ported earlier). Source check 26's
liveness-probe sub-point lands inside THIS file's existing check
19, as a new lettered sub-point, rather than as its own numbered check
(its subject -- hook-code liveness -- is a posture detail of check 19's
own gate list). Source check 1's designer-threshold / resubmission
sub-points land inside THIS file's existing check 1, as sub-points (c)/
(d), for the same reason. Source checks 15/17/27/28 are NOT ported (15
duplicates this file's own already-ported check 15; 17 is a reserved
placeholder in both files independently; 27/28 are specific to a
sibling deployment this deployment does not run).

20. **Leaf-routing judge acceptance (rule 13).** Mechanism: rule 13 of
    CLAUDE.md's core policy, a `"judge"` value in the journal
    validator's `BASIS_VALUES`, and the judge-acceptance tooling class
    it depends on. Window check: (a) liveness -- rule 13 is present in
    CLAUDE.md; `"judge"` is in the validator's basis whitelist; judge
    calibration is alive (full agreement on the labeled set in
    gateway/judge_calibration.json, procedure in PROCESS/
    JUDGE_CALIBRATION_PROTOCOL.md). BOTH judge forms in use this window
    are checked: the gateway alias, and any subscription judge-subagent
    -- the subagent's system prompt is VERBATIM equal to
    `JUDGE_SYSTEM_PROMPT` in gateway/shadow_eval.py (a drifted prompt is
    a finding, not a judge), and the equivalence run itself is on
    record (journal or the calibration protocol's own log). (b)
    event-by-event -- every `accepted` carrying `basis: "judge"` is
    genuinely leaf-class (recon, or implementation to a written spec);
    a mechanism/policy/integration accepted under a judge basis is a
    self-certification finding (the same class as a role-vs-tier
    violation, CLAUDE.md's "Role != tier"); spot-check judge reject/
    accept rationales for hallucination (citing a symbol or file that
    does not exist) -- a systematic pattern is grounds to reconsider the
    judge binding by an explicit decision, never silently. (c)
    economics -- the window's judge calls cost a small fraction of the
    coordinator-tier acceptance they stand in for (Rule #1); a rising
    share of failed-after-escalation leaf tasks is a finding about the
    construction itself, not about one task. (d) siblings -- any
    deployment-specific judge/leaf-routing queue entries have not gone
    stale.
21. **Durable persistence of accepted deliverables (session-handoff
    step 2a).** Class: "deliverable drift" -- work accepted against the
    working tree (a real witness at the time) gets washed out by a
    later wide checkout/reset before the commit that should have
    carried it, and neither the witness nor a critic verdict re-checks
    persistence after the fact. Window check: (a) for every
    `accepted(builder)` in the journal, the entity the witness names (a
    test, a function, a file) exists in the COMMITTED HEAD (`git show`
    / grep against HEAD; on doubt, `git log -S` by name -- a carrying
    commit exists and was not reverted). A real witness with the entity
    absent from HEAD is drift -- a finding, plus a `defect_found` (`ref`
    pointing at the original `accepted`). (b) liveness of the
    evening-side check -- session-handoff's step 2a is in place (a
    targeted lookup, not a re-derivation); systematic drift while step
    2a is live and being run is a discipline leak -- evidence for
    promoting the check into a code gate. (c) a disputed "did the
    artifact ever exist" is settled by runtime witnesses outside git (a
    test-cache entry, a file mtime, a process/track log) -- the same
    forensic class as the check above.

22. **Ledger drift and completeness.** Mechanism: the
    adoption ledger records the kit snapshot revision and mirrors the
    current template's row nomenclature; an upgrade is a
    re-inventory BY DELTA-PER-REVISION — new/changed mechanisms since
    the recorded revision, including role-file CONTENT (not just
    their model: frontmatter), skills, tools, PROCESS; a full rescan
    applies only when no revision is recorded (a pre-versioning
    install, one-off). Violation: an "adopt" row
    whose mechanism is absent or stale in the tree; a template row
    missing from the ledger entirely (a dropped row hides forever —
    the class of a row silently dropped from the host's own mirror of
    the template nomenclature); a recorded revision no upgrade batch
    has reconciled. Window check: (a) every current template row has a
    ledger row (completeness); (b) spot-check adopt rows against the
    tree (mechanism present, wired); (c) the recorded kit revision
    exists, and the last upgrade batch's delta was decided row by
    row — at least deferred, silence is not a decision. For (b),
    "wired" is explicit (wiring drift): the row's mechanism
    is not just present on disk but actually wired — its hooksPath
    entry / settings hook / invocation path exists; an adopt row
    whose wiring silently fell off is a finding even when the file
    itself is still in the tree. Continuous pair of (b): the
    deployment's SessionStart wiring check reads this ledger's adopt
    rows, not only the configured hooks. The counterpart of this
    check, on the side of whoever maintains the kit you're adopting
    from, is their own port-batch delta check (their calibration
    protocol).

23. **Closing out the previous run (retro-contour).** Open the notes
    of the last `calibrated` event and that run's findings: each is
    closed by a mechanism/decision, OR sits queued with a NAMED
    trigger that has not fired yet. A queue item (the CURRENT_CONTEXT
    queue, or the deployment's FINDINGS log) whose trigger fired, with
    the work neither started nor re-decided, is a finding OF THE
    CURRENT run. Sources: the journal's `calibrated` events, the
    FINDINGS log for the window, the CURRENT_CONTEXT queue. A fresh
    deployment with no prior `calibrated` event has nothing to close —
    note it explicitly: "no previous run".

24. **Gate walk by `defect_found`.** For each `defect_found` of the
    window: list the gates that stood on the path of the defect
    (witness, the critic entry, trail-based acceptance, code gates),
    and name which stayed silent and why (a discipline leak / a check
    blind spot / a new class). A silent gate is a finding and a
    candidate for promotion into a code gate (rule 10's
    code-gates-execution clause); the breakdown line goes into the
    `calibrated` event's notes. An empty window (0 `defect_found`) is
    noted explicitly.

25. **Cost crossover of escalations (Update Rule 4 of the assignment
    table).** For every escalated task of the window (`escalated` plus
    its `task_id` chain): the actual full cost of every attempt
    (sidechains of the attempts, plus Lead overhead of acceptance)
    against the estimate of a direct dispatch to the tier where the
    task was accepted. A systematic loss by category (a cheap tier
    with retries costing more) is evidence for revising the delegation
    boundary (a table row / rule 6). An empty window (0 escalations)
    is noted explicitly.

26. **Freshness of navigation documents.** Direct pass: window events
    (phase/task closures, decisions, status moves — from the journal
    and git log) are reflected in their OWNER documents: DECISIONS.md
    (decisions), CURRENT_CONTEXT.md (the live task/queue),
    DELEGATION_TABLE.md (tier statuses), README.md (navigation),
    docs/SIBLING_MAP.md (the axis map). OWNERSHIP PASS: the same list
    of owners is read in REVERSE — for every block of the boot-path
    files, ask "is this fact at its OWN owner?" A block whose owner is
    a DIFFERENT document is a finding of the same class even when it's
    fresh and not duplicated: it is paid for by every session, but
    lives in the wrong place. Separately verify that a calibration
    run's OWN findings land in the `calibrated` event's notes, and
    CURRENT_CONTEXT keeps only the UNRESOLVED decision, one line per
    item — a finding written to the journal AND duplicated in prose in
    the queue bloats the live file and evades the boot-diet skill's
    size/dedup steps, since it is neither closed nor a duplicate of
    another boot file. Reverse pass: load-bearing claims of the boot
    path ("waiting on X", "next is Y", dates) are spot-checked against
    fact; a stale claim is a finding of this same class. The verdict
    is a semantic judgment for the calibrating Lead; a weekly cadence
    is enough. Distinct from check 10: that one watches the SIZE of
    live files, this one watches whether their CONTENT still matches
    fact, and whether it lives in the right place. Execution: both
    passes are carried out by a scout dispatch (walking documents is
    recon, rule 1); DoD — a line-by-line verdict "fresh / staleness
    candidate" per document with a trail, "no staleness" is a valid
    outcome with a trail; digest acceptance follows the trail-based
    acceptance rule. An off-cycle run of this check is legal at any
    time on the operator's word. A fresh deployment with no closed
    phases/decisions yet has nothing to check against — note it
    explicitly: "no events to reconcile".

27. **Permission/hygiene audit of the window.** Run
    `python tools/permission_audit.py --minutes <window>` (or `--all`)
    against transcripts of the period; the walkthrough steps are
    `.claude/skills/permission-audit/SKILL.md`. `--summary` prints the
    "hygiene class breakdown" — a count by the FOUR classes (`2>&1`,
    `cd`/`Set-Location`, `python -c`/heredoc, "journal bypassing
    Edit/Write") across ALL scanned calls, with the suspect sub-count
    alongside each, plus a "commands with >=1 class" line. The first
    run of this check records ITS OWN baseline (there is no prior data
    point on a fresh deployment); later runs compare against it. An
    empty window (no transcripts, or a fresh deployment with none yet)
    is noted explicitly — "no calls to audit". Two categories: (a)
    hygiene VIOLATIONS themselves (the right-hand column of the
    skill's step 2 table: a `cd` prefix/`2>&1`, a hand-built journal
    line bypassing Edit/Write, an ad-hoc read bypassing Read/Grep,
    bypassing the canonical pytest form, poll loops, a RELATIVE NUMBER
    WITH NO NAMED BASE, a REGISTRY ENTRY'S STATUS CLAIMED FROM A
    PARTIAL READ (command hygiene point 6: the entry's status line was
    never reached)) — fix at the source; the count and class go into
    the calibration report. (b) `settings.local.json` curation
    (MASKED-by-broad-allowlist rules, duplicates, one-off entries) —
    the skill's steps 3-5; narrowing broad rules is an operator
    decision.
    (c) UNSAFE ROLLBACK OF CORRUPTION: window transcripts are searched
    for `git checkout --` / `git restore` NEAR a mutation probe (a
    file corruption, a red-probe, "corrupt then restore"). Every hit
    is checked: was a byte copy taken BEFORE the corruption, and was
    the file clean per `git status --porcelain` beforehand? If not,
    that is a violation of command hygiene point 7 (the byte-copy
    rollback rule), and a finding — independent of whether harm
    actually occurred that time. A positive-form control of the search itself
    is mandatory (command hygiene point 6). An empty window (no
    rollback-adjacent `git checkout`/`git restore` calls found) is
    noted explicitly — "no rollback events".
    (d) THE "TRUNCATED REGISTRY WINDOW -> STATUS CLAIM" LINK: an
    address scan of window transcripts for the combination of reading
    a registry (escalations/decisions/tasks/ledgers) through a
    truncated/limited window (a `Read` with `limit`/`offset`, a
    headline grep that never reaches the entry's status line) followed
    by a status claim about that SAME entry in a summary or report
    with NO re-read of the status field. A hit is a finding plus a
    reminder of command hygiene point 6. HONEST CAVEAT: this class's
    base detector is INCIDENTAL (an operator's question exposes the
    mismatch by fact, not by rule) — this transcript scan only
    SUPPLEMENTS the incidental layer, it does not replace it with a
    machine one; do not present one as the other. An empty window (the
    combination never occurred) is noted explicitly — "no truncated
    status claims".

28. **Completeness of workers' final messages.** Mechanism: the rule
    "the final message is the FULL report/digest/verdict, and a
    resubmission restates it from scratch" lives in the role files
    (`.claude/agents/builder.md` point 7, `scout.md` point 9,
    `critic.md` point 16, `designer.md` point 5, `judge.md` point 3)
    plus the resubmission hint in `tools/dod_gate.py`'s
    `BLOCK_MESSAGE` (substring "COMPLETE final report"). Window check:
    (a) liveness — the five anchors are in place (a point lookup); (b)
    failure — window events marked with a content re-request ("repeat
    the report", "re-requested", "prior messages not delivered") in
    journal notes, AND/OR a usage-record sidechain with a large volume
    of work whose final message is empty or truncated, is a leak of
    the rule — a finding. The first window that measures this records
    its OWN baseline (rate per day/week); later windows compare
    against it — growth is grounds to revise the mechanism's form (a
    candidate: a code layer on SubagentStop, the same class dod_gate
    already applies on Stop), a decline toward zero is the healthy
    direction. (c) siblings — every role file on Axis 1 of
    `docs/SIBLING_MAP.md` carries the rule; a new tier/role file added
    later gets the same line in the same commit (Axis 1's own
    same-commit maintenance duty) — a role file missing it is a
    finding of this check, not just of Axis 1's own upkeep. An empty
    window (no re-request events, no truncated-message sidechains) is
    noted explicitly — "no re-requests".

29. **Upgrade delivery by delta-per-revision — the REDISTRIBUTOR
    side.** Applicable ONLY when this deployment itself further
    redistributes its (adapted) copy of the template to one or more
    downstream sub-deployments; a deployment that only ADOPTS from an
    upstream kit and never ships its own template onward has nothing
    to check here — note explicitly "not applicable: this deployment
    does not redistribute" and stop. The RECEIVING side of the same
    duty (this deployment reconciling deltas from whatever it adopted
    FROM) is check 22 above — do not conflate the two directions.
    Mechanism, mirrored outward: a port-batch shipped to a downstream
    sub-deployment is assembled as a delta from that sub-deployment's
    OWN recorded snapshot revision of your template; role files travel
    as diffable CONTENT of the delivery, not just their `model:`
    frontmatter. Violation: a batch shipped with new/changed
    mechanisms since the recorded revision carrying no corresponding
    ledger-delta lines in the target's own carrier — a mechanism
    invisible to the delivery (role-file content changes are the
    highest-risk case: a content-only edit with no frontmatter change
    can stay invisible to a delta check that only looks at
    frontmatter, and the blind spot can live for a long time before
    anyone notices). Window check, per outgoing port-batch: (a) the
    target's recorded snapshot revision exists; (b) your delta from
    that revision (a diff of your own template tree) is matched,
    position by position, against the ledger-delta lines in the
    target's handoff carrier — an uncovered position is a finding; (c)
    accepted role changes at the target are accompanied by their own
    exam gate; (d) SEALED DELIVERY OF THE CONTROL CHAIN: a delta
    position that changes an EXECUTABLE file of the control chain (a
    git hook, a hook script invoked by one) carries the FULL target
    content, not a delta line; the batch's acceptance carries a
    liveness-probe witness (an invalid input is rejected, and the
    probe state is rolled back afterward); and the target's required
    hook files land in git's index at mode 100755 — a mode of 100644
    ships a silently dead gate on Linux even though the file itself is
    present and looks installed. An empty window (no port-batches
    shipped in the period) is noted explicitly — "no outgoing
    batches".

## Closing out a run

DELEGATION_TABLE.md statuses move only on this data (Update Rule 1;
full cost including retries — Update Rule 4). On completion, write a
`calibrated` event to the journal: notes carry the period, the number
of events reviewed, table status changes, the check-10 line counts,
the check-11 hook output size, the check-13 false-accept rate by tier,
and the check-18 economic numbers (against the previous data point).
No `calibrated` event for more than 7 days while routed traffic is
live is itself a violation, visible as a Last Calibration line in
every session's Boot Report (the detector lives outside this protocol
on purpose: calibration cannot be the detector of its own absence).
