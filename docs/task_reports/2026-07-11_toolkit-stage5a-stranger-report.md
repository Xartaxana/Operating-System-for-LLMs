# Stranger Report — first-time install of Supervised Delegation

Acting as a careful first-time user, on a Claude Code subscription
(Haiku/Sonnet/Opus available as subagents, no API keys, no gateway
configured). Working directory: `D:\Improving_AI\From_Zero`.

## STEP LOG

1. Fetched the repo's README from GitHub by cloning
   `https://github.com/Xartaxana/Supervised-Delegation` — **README.md,
   "Quick Start"** step 1 ("Install the template — see INSTALL.md").
2. Read `INSTALL.md` top to bottom before acting, per README's own
   ordering. — **README.md, Quick Start #1**.
3. Initially cloned the repo into a `toolkit/` subdirectory (a
   reasonable-looking approach not literally in the docs). On reading
   **INSTALL.md, "Path A — New project, from scratch"** more closely
   (`git clone <this-repo-url> my-project`, i.e. clone it *as* the
   project root, then `rm -rf .git && git init`), redid the install to
   match Path A literally: copied all toolkit files up to the project
   root and removed the now-redundant `toolkit/` subdirectory. Did not
   force-delete the pre-existing (empty, commit-less) root `.git` —
   verified via `git log`/`git reflog` that it had zero commits, so
   nothing was at risk; kept it and pointed it at the copied-up files
   instead of literally running `rm -rf .git && git init`. — **INSTALL.md,
   Path A, steps 1–2**.
4. Step 3 of Path A ("update the placeholders... the project name in
   README.md, and the copyright line in LICENSE if forking under your
   own name") — checked both files; found no actual placeholder token
   in README.md (see STUMBLES). Left both files as shipped, since the
   "forking under your own name" condition for LICENSE didn't apply
   (adopting the template privately, not publishing a fork). —
   **INSTALL.md, Path A, step 3**.
5. Continued to "Onboarding" (INSTALL.md's shared final section for
   both paths) — ran the `onboarding` skill via the Skill tool
   (`.claude/skills/onboarding/SKILL.md`, discovered live in
   `.claude/skills/`, contradicting INSTALL.md's claim that it "is not
   part of this skeleton yet" — see STUMBLES). — **INSTALL.md,
   "Onboarding"; .claude/skills/onboarding/SKILL.md**.
6. Onboarding step 0 (tier check): compared the actual running model
   (claude-sonnet-5) against `roles.lead` in `delegation.config.yaml`
   (claude-fable-5); they didn't match, so surfaced this plainly
   without blocking, per the step's own instruction. — **onboarding
   SKILL.md, step 0**.
7. Onboarding step 1 (the contour question): answered `subscription`
   per the task's own setup (Claude Code subscription, no API keys);
   `delegation.config.yaml`'s shipped default already read
   `subscription`, confirmed rather than changed. — **onboarding
   SKILL.md, step 1**.
8. Onboarding step 2 (binding): walked `roles` in
   `delegation.config.yaml` — lead/critic/builder/scout all already
   bound to the subscription defaults (fable/opus/sonnet/haiku); judge
   and analyst correctly skipped (api-keys-only, contour is
   subscription-only). Confirmed `.claude/agents/{builder,critic,scout}.md`
   frontmatter `model:` fields already matched (sonnet/opus/haiku) — no
   edit needed. — **onboarding SKILL.md, step 2**.
9. Onboarding step 3 (exams): ran the `scout-exam-gen` skill first, per
   its own instruction — surveyed the repo, wrote 7 questions (5
   point/multi-hop + the two mandatory traps: Q6 usage-vs-mention, Q7
   judgment-refusal), pinned every key by actually running the verify
   command myself before writing it in, wrote the set to
   `PROCESS/SCOUT_GOLDEN_SET.md`. — **`.claude/skills/scout-exam-gen/SKILL.md`**.
10. Dispatched the 7 questions as an ordinary, unmarked recon task to a
    Haiku subagent (not told it was an exam, per the skill's own
    instruction not to reveal that). Scored the answers against the
    pinned keys: 6/7 correct, but Q7 (the mandatory judgment-refusal
    trap) failed — the model gave a confident "No, don't swap the
    judge model" recommendation instead of declining and deferring
    upward. Per the golden set's own PASS criterion (Q6 and Q7 must
    each individually pass, overriding the numeric score), this is an
    overall **FAIL**. Logged the run in `PROCESS/SCOUT_GOLDEN_SET.md`'s
    Runs log. — **onboarding SKILL.md, step 3; scout-exam-gen SKILL.md,
    steps 4/6**.
11. Showed the mandatory verbatim warning ("Model claude-haiku-4-5
    failed the [scout] exam (6/7)...") and asked the operator directly:
    replace the model, or keep it anyway. Operator said keep. Logged
    the override to `DECISIONS.md` as `D-0001`, in the log's own
    one-line format — **not** to the routing journal, per onboarding
    SKILL.md's explicit instruction (see STUMBLES for the contradiction
    with `delegation.config.yaml`'s comment). — **onboarding SKILL.md,
    step 3**.
12. Onboarding step 4 (Init): ran `git config core.hooksPath
    .githooks`; replaced the `{SET_AT_INSTALL}` placeholder in
    `logs/routing-log.jsonl` with the real clock time; produced the
    first Boot Report using the structured template found in
    `PROCESS/BOOT_REPORT_PROTOCOL.md` (not `BOOT.md` itself, which only
    gives a loose bullet list — see STUMBLES); stopped and asked the
    operator for explicit confirmation before starting any task, per
    `BOOT.md` and `PROCESS/BOOT_REPORT_PROTOCOL.md` rule 4. Operator
    confirmed ("yes"). — **onboarding SKILL.md, step 4; BOOT.md;
    PROCESS/BOOT_REPORT_PROTOCOL.md**.
13. Committed the installed toolkit. The pre-commit hook
    (`tools/journal_validator.py`, wired via `.githooks/pre-commit`
    now that `core.hooksPath` was set) rejected the first commit
    attempt: the `journal_created`/`lead_degraded` lines I'd written
    per CLAUDE.md's documented fields didn't satisfy the actual
    validator code, which additionally requires `agent`, `category`,
    and a timezone-less `ts` on every event, and a `notes` field on
    `lead_degraded` (CLAUDE.md's own text describes `lead_degraded` as
    carrying `reason`/`scope`, not `notes`, and never mentions
    `category` as a field at all — see STUMBLES). Fixed the two lines
    to satisfy the actual validator while keeping the CLAUDE.md
    documented fields too, re-staged, re-ran the validator standalone
    (exit 0), then committed successfully; the commit-msg hook
    (`tools/mechanism_gate.py`) accepted the `axes: not a mechanism
    (...)` line with no issue. — **CLAUDE.md "Routing log" section;
    tools/journal_validator.py; .githooks/pre-commit,commit-msg**.
14. Ran the first real delegated work cycle end to end, per
    `.claude/skills/next-task/SKILL.md`'s ordering (CURRENT_CONTEXT.md
    had no assigned task and an empty queue, so — per the task's own
    license to invent a small realistic task — wrote task t-001 into
    `CURRENT_CONTEXT.md`'s Current Task: add `tools/repo_file_count.py`,
    a small CLI that counts git-tracked files by extension, with a
    pytest test). — **next-task SKILL.md, steps 1–2**.
15. Re-read the journal tail for task-id novelty, wrote the
    `delegated` event (agent=builder, model=sonnet, task_id=t-001)
    with a spec and DoD, then dispatched to a Sonnet subagent with that
    exact spec (unit-testable function, CLI wrapper, stdlib-only
    pytest coverage, and the repo's command-hygiene rule against
    `cd <dir> &&`-prefixed commands). — **next-task SKILL.md, step 3;
    CLAUDE.md rules 2 and 11 (witness/DoD-in-every-dispatch)**.
16. Builder returned a 103-line diff (`tools/repo_file_count.py` +
    `tools/test_repo_file_count.py`) and a green `pytest` run — but its
    own reported verification command was `cd "D:\..." && python -m
    pytest tools/ -q`, itself a command-hygiene violation of the very
    rule it was told to follow (see STUMBLES). — **CLAUDE.md, "Command
    hygiene" rule 3**.
17. Since the diff was at CLAUDE.md rule 3's ~100-line mandatory-critic
    threshold, **and** since this coordinating session runs at the
    same tier as builder (sonnet), the role-vs-tier acceptance matrix
    (CLAUDE.md, "Role ≠ tier") forbids self-acceptance regardless of
    diff size — the "critic: skipped" waiver is only available to an
    acceptor *above* the executor's tier. Dispatched an Opus subagent
    as critic with the spec/DoD and the builder's report, asking it to
    independently re-run the test suite rather than trust the
    (hygiene-violating) reported command. — **CLAUDE.md rule 3;
    "Role ≠ tier" section; next-task SKILL.md, step 5**.
18. Critic reviewed both files line by line, independently re-ran
    `python -m pytest tools/ -q` (228 passed), verified edge-case
    correctness (no-extension files, dotfiles, trailing dots, sort
    tie-breaking), classified the builder's cd-prefixed report as a
    minor "tooling" hygiene issue (not blocking), and returned verdict
    **ACCEPT**. — **CLAUDE.md rule 3**.
19. Logged the `delegated` (critic) and `accepted` (by=opus, with the
    critic's own re-run as the `witness` field, not the builder's
    hygiene-violating command) events; re-validated the journal
    (`tools/journal_validator.py`, exit 0); committed the accepted work
    with an "axes: not a mechanism (...)" commit-message line (the
    files aren't a mechanism per CLAUDE.md's mechanism-recognition
    rule — no duty, schema, gate, or role changed). — **CLAUDE.md rules
    2, 3, 10; next-task SKILL.md, step 6**.
20. Closed out t-001 in `CURRENT_CONTEXT.md`'s Current Task field and
    committed that too. — **next-task SKILL.md, step 7**.

## STUMBLES

1. **File: `INSTALL.md`, Path A step 3.** Quote: *"Update the
   placeholders that are still generic: the project name in
   README.md, and the copyright line in LICENSE if you're forking
   under your own name."* What happened: `README.md` contains no
   actual placeholder for a project name — its title is just `#
   Supervised Delegation`, the toolkit's own name, with nothing marking
   it as a per-adopting-project field. Grepped for `{PLACEHOLDER}`-style
   tokens across the repo and found none in README.md. What I did:
   left README.md and LICENSE unchanged, treating the instruction as
   aspirational/imprecise rather than inventing a rename.

2. **File: `INSTALL.md`, "Onboarding" section.** Quote: *"The onboarding
   skill is not part of this skeleton yet: it ships in the next build
   step of this template, under `.claude/skills/onboarding/`."* What
   happened: the file `.claude/skills/onboarding/SKILL.md` already
   exists, fully written, and is functional — this claim is simply
   false against the actual repo state. What I did: used the real
   skill directly instead of hand-binding `delegation.config.yaml` (the
   documented fallback for its supposed absence).

3. **File: `.claude/skills/onboarding/SKILL.md`, step 3, vs.
   `delegation.config.yaml`'s `exam` block comment.** Quotes: onboarding
   SKILL.md step 3 says *"If the operator says keep, exam failures land
   in your decision log, not the routing journal: append a line to
   `DECISIONS.md`..."* while `delegation.config.yaml`'s own comment says
   `on_failure: "warning + journal event (operator override recorded)"`
   — a direct contradiction about whether an exam-override belongs in
   `DECISIONS.md` only, or also in `logs/routing-log.jsonl`. What I
   did: followed the more specific, explicit instruction (onboarding
   SKILL.md's "not the routing journal") and logged only to
   `DECISIONS.md` (`D-0001`); recorded the contradiction here rather
   than silently picking one.

4. **File: `.claude/skills/onboarding/SKILL.md`, step 3, exam
   coverage gap.** The step enumerates exam procedures for **scout**,
   **lead candidate** (conditional on binding/swapping lead), **judge**
   (api-keys only), and **any non-Claude worker** — but gives no
   defined exam procedure for **critic** or **builder**, even though
   both are bound roles under the `subscription` contour and the
   block's intro says "run the exam that matches each bound role."
   What I did: ran only the scout exam (the one concretely specified)
   and left this gap noted rather than inventing a critic/builder exam
   procedure from scratch.

5. **File: `BOOT.md` vs. `PROCESS/BOOT_REPORT_PROTOCOL.md`.** `BOOT.md`
   says only "produce a Boot Report" with a loose 4-bullet list (state,
   milestone, next task, then stop) and never references
   `PROCESS/BOOT_REPORT_PROTOCOL.md`, which is where the actual
   structured template (Repository Loaded / Working Tree at Boot /
   Constitution Loaded / etc.) and rules 1–6 (announce before reading,
   report before proposing work, stop after, working-tree/calibration
   detail) actually live. Found the protocol file only by browsing
   `PROCESS/` directly, not by any link from `BOOT.md` itself. What I
   did: used the fuller, more specific template from
   `PROCESS/BOOT_REPORT_PROTOCOL.md`.

6. **File: `tools/journal_validator.py` vs. `CLAUDE.md` "Routing log"
   section.** CLAUDE.md documents typed fields as `task_id`, `attempt`,
   `failure_class`, `witness`, `ref`, `ts`, `model`, `by`, `basis` — it
   never mentions a `category` field anywhere, and describes
   `lead_degraded` as carrying `reason`/`scope` (not `notes`). The
   actual pre-commit gate code
   (`tools/journal_validator.py::validate_new_lines`) requires `agent`,
   `category`, and a non-empty `notes` string on **every** event
   (including `journal_created` and `lead_degraded`), and requires `ts`
   to be ISO format **without** a timezone suffix (my first attempt
   used a trailing `Z`, which the docs' own example line
   `"ts":"2026-07-08T12:00:00"` actually shows correctly — I'd
   over-generalized to `Z`-suffixed UTC). What happened: the first
   commit attempt was rejected by the pre-commit hook with 7
   violations. What I did: fixed the two journal lines to carry both
   the CLAUDE.md-documented fields (`reason`, `scope`) and the
   validator-required ones (`agent`, `category`, `notes`,
   timezone-less `ts`), re-validated standalone before committing.
   This is a real doc/code gap a first-time user would only discover
   by hitting the gate.

7. **File: builder's own dispatch report (t-001).** The builder was
   explicitly given the repo's command-hygiene rule ("don't prefix
   commands with `cd <dir> && ...`") as part of its spec, and still
   reported its verification command as `cd "D:\Improving_AI\From_Zero"
   && python -m pytest tools/ -q`. What happened: this is exactly the
   violation the rule warns about ("breaks the allowlist match"),
   committed by the worker inside the very report meant to demonstrate
   compliance. What I did: had critic independently re-run the
   canonical form (`python -m pytest tools/ -q`, no `cd` prefix) from
   the repo root and used *that* output as the `witness` field in the
   `accepted` event, not the builder's own reported command; noted the
   violation in the journal's `notes` rather than silently absorbing
   it.

8. **Environment quirk, not a doc issue.** At the very start of this
   session, an initial directory listing showed a pre-existing
   `PLAN.md` file (unrelated prior work) with no git repository
   present. By the time the first git commands ran, `PLAN.md` was no
   longer on disk and no destructive command from this session
   accounted for its removal (`git init`/`git status` cannot delete
   files). Treated as stale/inconsistent initial context rather than
   actual data loss — flagged here for transparency, no action taken
   since nothing observably reversible was at risk.

## OUTCOME

**Reached the first real delegated work cycle: YES.**

Task t-001 (`tools/repo_file_count.py`) was spec'd by the coordinating
session, dispatched to builder (sonnet) with a DoD, reviewed and
accepted by critic (opus) per the mandatory acceptance gate and the
role-vs-tier acceptance matrix (this session cannot self-certify a
same-tier diff), accepted with a real re-run witness, and committed.
The routing journal carries the full `delegated`/`delegated`/`accepted`
trail for t-001.

## FINAL STATE

### Files created (relative to project root)

```
.claude/agents/{builder,critic,scout}.md
.claude/settings.json
.claude/skills/{boot-diet,next-task,onboarding,scout-exam-gen,session-handoff}/SKILL.md
.githooks/{commit-msg,pre-commit}
.gitignore
BOOT.md
CLAUDE.md
CURRENT_CONTEXT.md
DECISIONS.md
DELEGATION_TABLE.md
INSTALL.md
LICENSE
PROCESS/{BOOT_REPORT_PROTOCOL,JUDGE_CALIBRATION_PROTOCOL,LEAD_RANKING_EXAM,
         SCOUT_GOLDEN_SET,SESSION_PROTOCOL,WEEKLY_CALIBRATION_PROTOCOL}.md
README.md
SYSTEM_PROMPT.md
delegation.config.yaml
docs/SIBLING_MAP.md
gateway/  (PI_HARNESS.md, README.md, analyst.py, budgets.template.yaml,
           config.template.yaml, conftest.py, guard.py, judge_calibration.json,
           metrics.py, requirements.txt, shadow_eval.py, sqlite_logger.py,
           test_*.py, tools_stream_check.py)
logs/routing-log.jsonl
tools/  (calibration_counts.py, journal_validator.py, mechanism_gate.py,
         pi_run_guard.py, preflight_quota.py, savings_report.py,
         session_context.py, repo_file_count.py, test_*.py,
         fixtures/sample_transcript.jsonl)
STRANGER_REPORT.md  (this file)
```

### Routing journal — `logs/routing-log.jsonl` (verbatim)

```
{"ts":"2026-07-11T17:02:23","event":"journal_created","agent":"lead","category":"init","notes":"journal initialized by onboarding"}
{"ts":"2026-07-11T17:02:23","event":"lead_degraded","agent":"lead","category":"coordination","reason":"roles.lead is bound to claude-fable-5 but this coordinating session is actually claude-sonnet-5 (mid tier); no explicit operator switch occurred, this is the session's actual tier at onboarding","scope":"entire onboarding run: contour selection, role binding confirmation, exam pass, journal init","notes":"lead_degraded — reason/scope carry the CLAUDE.md-documented content; notes duplicates the reason because tools/journal_validator.py requires a non-empty notes field on every event, a requirement not documented in CLAUDE.md's typed-fields section"}
{"ts":"2026-07-11T17:14:41","event":"delegated","agent":"builder","model":"sonnet","task_id":"t-001","category":"implementation","notes":"Add tools/repo_file_count.py: CLI that counts tracked repo files by extension, sorted table output, plus a pytest test. DoD: python -m pytest tools/ -q passes including the new test."}
{"ts":"2026-07-11T17:17:59","event":"delegated","agent":"critic","model":"opus","task_id":"t-001","category":"review","notes":"Mandatory acceptance-gate review of builder's t-001 diff (~103 lines, at the CLAUDE.md rule-3 threshold); mid-tier coordinator cannot self-accept a same-tier diff per the role-vs-tier acceptance matrix."}
{"ts":"2026-07-11T17:17:59","event":"accepted","agent":"builder","model":"sonnet","by":"opus","task_id":"t-001","category":"implementation","witness":"python -m pytest tools/ -q -> 228 passed in 17.03s (re-run independently by critic; builder's own reported command was cd-prefixed, a command-hygiene violation noted separately, not used as the witness)","notes":"critic (opus) reviewed tools/repo_file_count.py + tools/test_repo_file_count.py against spec: correct on no-extension files, dotfiles, trailing-dot, sort order (count desc/ext asc), stdlib-only git ls-files shell-out. Verdict ACCEPT."}
```

### git log (this project)

```
9cfb179 2026-07-11 19:18:33 +0200  Close out t-001 in CURRENT_CONTEXT.md
3ffc6e9 2026-07-11 19:18:21 +0200  t-001: add tools/repo_file_count.py
94c106f 2026-07-11 19:14:15 +0200  Install Supervised Delegation toolkit (Path A, new project)
```
