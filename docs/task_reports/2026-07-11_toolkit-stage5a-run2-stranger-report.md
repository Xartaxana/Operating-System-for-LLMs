# Stranger Report — adopting Supervised Delegation into a fresh project

Setup: Claude Code subscription only, no API keys, no external gateway.
Starting point: this directory, git already initialized, otherwise empty.
Toolkit: https://github.com/Xartaxana/Supervised-Delegation (README/INSTALL
fetched via raw.githubusercontent.com + the GitHub contents API; `gh` CLI
was unauthenticated in this environment).

## STEP LOG

1. **[README.md, "Quick Start"]** Fetched the README. It points to
   INSTALL.md for the two install paths and states the one onboarding
   question up front ("Claude Code subscription, or API keys — 'both' is
   valid").
2. **[INSTALL.md, "Path A — New project, from scratch", step 2]** This
   project is an empty, git-initialized folder — exactly the case
   INSTALL.md's own step 2 calls out as not matching the literal
   instructions. Followed its own prescribed workaround: cloned the
   template into a temporary subfolder (`.sd-template-tmp`), moved its
   files into the project root, deleted the temp clone's own `.git`, and
   left the project's original `.git` untouched (no `git init`).
3. **[INSTALL.md, Path A step 3]** Left README.md's title as-is (no
   literal placeholder token to replace, per the doc's own note). Did not
   change LICENSE's copyright line since this isn't being forked publicly
   under a new name.
4. **[INSTALL.md, Path B step 3-4, applied early]** Even though this was
   a Path-A install, `.githooks/` and the routing journal shipped as part
   of the whole-template copy, so I applied Path B's step 3
   (`git config core.hooksPath .githooks`) and step 4 (replace
   `{SET_AT_INSTALL}` with the real install time) before the first
   commit, since the rationale ("do this before your first commit of the
   journal") is not Path-specific.
5. **[tools/journal_validator.py, CLAUDE.md "Routing log" section]**
   Discovered the shipped seed `journal_created` line fails the repo's
   own validator (see Stumble 2). Fixed the seed line's fields and
   format before committing.
6. **[.githooks/commit-msg → tools/mechanism_gate.py, CLAUDE.md rule
   10(b)]** First commit attempt was blocked by the mechanism gate
   (touching CLAUDE.md/agents/PROCESS/etc. requires an axis-verdict
   block). Added the axis block to the commit message and committed
   (`8bfb8d2`, "Install Supervised Delegation template").
7. **[.claude/skills/onboarding/SKILL.md, step 0 "Tier check"]** Compared
   the model actually running this session (claude-sonnet-5) against
   `delegation.config.yaml`'s `roles.lead.subscription.model`
   (claude-fable-5, the shipped default). They don't match, and the
   running model is below the bound lead tier — surfaced this plainly
   per the skill's instruction, did not block on it.
8. **[onboarding SKILL.md, step 1]** Answered the contour question per
   this session's given setup: `subscription` (already the shipped
   default in `delegation.config.yaml`, confirmed rather than changed).
9. **[onboarding SKILL.md, step 2]** Walked `delegation.config.yaml`'s
   roles block; confirmed all shipped defaults (lead=claude-fable-5,
   critic=claude-opus-4-8, builder=claude-sonnet-5, scout=claude-haiku-4-5)
   against `.claude/agents/{scout,builder,critic}.md`'s `model:`
   frontmatter — already in sync, no edits needed. Skipped judge/analyst
   (api-keys-only, contour is subscription) and gateway/config.yaml
   generation.
10. **[onboarding SKILL.md, step 3, via .claude/skills/scout-exam-gen/
    SKILL.md]** Generated `PROCESS/SCOUT_GOLDEN_SET.md` (7 real
    file-anchored questions, keys pinned first) and dispatched it as an
    ordinary unmarked task to a haiku-tier subagent. Scored 7/7;
    contaminated (its own trail shows it read the golden-set file) but
    accepted per that file's own contamination rule (every answer still
    traced to a primary source outside it).
11. **[onboarding SKILL.md, step 3, via .claude/skills/critic-exam-gen/
    SKILL.md]** Ran the canonical test suite for the real baseline (311
    passed), wrote a seeded diff + pre-registered key to
    `PROCESS/CRITIC_EXAM.md`, dispatched to an opus-tier subagent.
    Attempt 1: correct REJECT with every finding right, but discarded as
    CONTAMINATED per critic-exam-gen's own (stricter, no-salvage) rule —
    the run stated outright that it had read the exam file. Attempt 2:
    fresh diff against a different file, scoped the dispatch away from
    PROCESS/docs; clean run, correct REJECT, verdict PASS.
12. **[onboarding SKILL.md, step 3, PROCESS/LEAD_RANKING_EXAM.md]** Ran
    the six lead-tier vignettes against a fable-tier subagent (12/12),
    then had an opus-tier subagent chief-judge the answers against the
    pre-registered rubric (12/12, PASS) — an explicit, logged deviation
    from the exam's own "chief judge one tier above the candidate" rule,
    since fable is already this deployment's top tier (see Stumble 5).
13. **[onboarding SKILL.md, step 4]** Committed all three exam artifacts
    plus the `calibrated` routing-journal entry (`92a21e7`), with the
    required axis block.
14. **[BOOT.md, PROCESS/BOOT_REPORT_PROTOCOL.md]** Produced the first
    Boot Report, then stopped per the protocol's rule 4 and waited for
    operator confirmation before starting real work.
15. **[operator: "go-ahead"]** Invented a small, real task (spec below),
    delegated it to a sonnet-tier builder subagent, got a real diff +
    witness (pytest run). Because the coordinating session (sonnet) is
    the SAME tier as the builder (sonnet), the "critic: skipped" waiver
    was unavailable (CLAUDE.md rule 3 / critic.md rule 9) — dispatched an
    opus-tier critic subagent for a real (non-exam) review. ACCEPT.
    Logged `delegated` and `accepted` events (task t-001) and committed
    the code + journal entries (`f64e34d`).

## STUMBLES

1. **File:** `INSTALL.md`, Path A, step 2.
   **Quote:** *"If your project folder already exists — empty, with `git
   init` already run in it — this step doesn't apply as written: clone
   the template into a temporary folder (or a subfolder) instead of
   directly into your project root, move its files into the root, and
   leave your existing `.git` alone (skip `git init`)."*
   **What happened:** This exactly matched my starting state (empty,
   git-initialized project). Not really an ambiguity — the doc
   anticipates this case explicitly — but worth flagging as the doc
   requiring the reader to notice their own situation doesn't match the
   *main* numbered step before finding the exception buried in the same
   list item.
   **What I did:** Followed the exception as written: temp clone →
   move files → drop the temp clone's `.git` → keep the original.

2. **File:** `logs/routing-log.jsonl` (as shipped) vs. `tools/
   journal_validator.py` and `CLAUDE.md`'s "Routing log" section.
   **Quote (shipped seed line):** `{"ts":"{SET_AT_INSTALL}","event":
   "journal_created","notes":"journal initialized by onboarding"}`
   **Quote (CLAUDE.md, line 183-186):** *"Every event line — including
   `journal_created` and `lead_degraded` — carries five base fields
   checked by `tools\journal_validator.py`: `ts`, `event`, `agent`,
   `category`, and a non-empty `notes`."*
   **What happened:** The template's own seed line, as shipped, is
   missing `agent` and `category` — both required by the same
   template's own pre-commit gate and its own policy document. The very
   first commit of the journal fails against the template's own rules,
   out of the box. Also: I initially wrote the replacement timestamp
   with a trailing `Z` (ISO-with-timezone) — `tools/journal_validator.py`
   explicitly forbids a timezone suffix (`TS_RE` has no `Z`/offset
   group), which CLAUDE.md also states directly ("`ts` must be ISO local
   time with NO timezone suffix — a trailing `Z` fails the gate") but
   only a few lines below the instruction that made me want to write
   ISO-8601 with `Z` in the first place.
   **What I did:** Added `"agent":"system","category":"meta"` to the
   seed line and dropped the `Z` suffix before the first commit.

3. **File:** `tools/mechanism_gate.py` / `.githooks/commit-msg` (rule
   10(b)), encountered via the first commit attempt.
   **What happened:** Not a bug — working as designed — but genuinely
   unknown until the gate rejected the commit and printed its own
   requirement. Neither INSTALL.md nor onboarding's SKILL.md mentions
   that touching `CLAUDE.md`/`.claude/agents/`/`PROCESS/`/etc. in a
   commit requires an "axis N: <verdict>" line for every axis in
   `docs/SIBLING_MAP.md`, or the literal skip phrase. A first-time
   installer's very first commit (which necessarily touches all of
   these paths, since it's installing them) hits this without warning.
   **What I did:** Read `tools/mechanism_gate.py` and
   `docs/SIBLING_MAP.md` directly, wrote a compliant axis block into the
   commit message.

4. **File:** `.claude/skills/critic-exam-gen/SKILL.md`, contamination
   rule, vs. `.claude/skills/scout-exam-gen/SKILL.md`'s contamination
   rule.
   **Quote (scout-exam-gen):** *"Accept a contaminated run only if every
   answer still traces to a primary source outside this file... ;
   otherwise re-run..."*
   **Quote (critic-exam-gen):** *"if the run's own trail shows the
   critic read `PROCESS/CRITIC_EXAM.md` itself... the run is
   contaminated — discard the result, regenerate a fresh diff and key,
   and re-run; don't try to salvage a contaminated verdict by reasoning
   about what it 'would have' found."*
   **What happened:** Not a contradiction exactly, but an asymmetry that
   cost a full extra exam cycle: scout's rule allows salvaging a
   contaminated run; critic's rule explicitly forbids it, even when (as
   happened here) every individual finding was independently correct.
   The first critic-exam dispatch, given the full repo to review,
   grepped broadly enough to surface `PROCESS/CRITIC_EXAM.md` itself and
   said so in its own output — an entirely correct REJECT verdict,
   thrown out anyway per the letter of the rule.
   **What I did:** Discarded attempt 1 per the rule, wrote a second,
   different seeded diff (against a different file), scoped the second
   dispatch's prompt away from `PROCESS/`/`docs/` to reduce the same
   risk, and re-ran. Attempt 2 was clean.

5. **File:** `PROCESS/LEAD_RANKING_EXAM.md`, "Rules of administration,"
   point 3.
   **Quote:** *"Judged by a chief judge one tier above the candidate."*
   **What happened:** The template's own tier order (`haiku < sonnet <
   opus < fable`, from `tools/journal_validator.py`'s `TIER_ORDER`) puts
   `fable` at the ceiling. `delegation.config.yaml` ships `lead` bound to
   `claude-fable-5` by default. Under a subscription-only contour with no
   API-key access to any other provider's frontier model, there is
   structurally no model above fable to serve as chief judge for a
   fable-tier lead candidate — and this exam document never addresses
   what happens when the candidate is already at the top of the known
   tier order. This is a real, standing gap for anyone running the
   subscription-only contour with the shipped default lead binding — not
   a corner case, but the DEFAULT configuration.
   **What I did:** Used opus (one tier below) as the best available
   substitute, logged the deviation explicitly and verbosely in both
   `PROCESS/LEAD_RANKING_EXAM.md`'s Runs log and the routing journal's
   `calibrated` entry, rather than silently proceeding as if the rule
   had been satisfied.

6. **File:** `CLAUDE.md`, "Routing log" section (example line) vs.
   `tools/journal_validator.py`'s rule 11 (role-vs-tier acceptance
   matrix).
   **Quote (CLAUDE.md example):** `{"ts":"2026-07-08T12:00:00","event":
   "delegated","agent":"builder","model":"sonnet",...}` — the `model`
   field in the doc's own canonical example is a bare TIER KEYWORD
   ("sonnet"), not a full model id.
   **What happened:** I initially wrote `"by":"claude-opus-4-8"` (a full
   model id, matching how I'd been writing the `model` field elsewhere,
   e.g. `"claude-sonnet-5"`) on an `accepted` event. The pre-commit gate
   rejected it: `journal_validator.py`'s rule 11 requires `by` to be one
   of the literal tier keywords in `TIER_ORDER` (`haiku`/`sonnet`/
   `opus`/`fable`) so it can compare tiers numerically — a full model id
   like `"claude-opus-4-8"` doesn't match any `TIER_ORDER` key and always
   fails the tier comparison silently (no crash, just `by_tier = None` →
   always fails). Neither CLAUDE.md's prose nor its own example makes
   this format distinction explicit between `model` (seemingly free-form,
   informational) and `by` (a strictly-enumerated tier keyword,
   mechanically checked) — I only found it by reading the validator's
   source after the commit was rejected.
   **What I did:** Changed `by` to the tier keyword `"opus"`. Left
   `model` fields elsewhere as full model ids (e.g. `"claude-sonnet-5"`),
   since the validator never actually constrains `model`'s format and a
   real model id is more useful there for future calibration — but this
   is a judgment call the docs don't settle either way.

## OUTCOME

**Reached the first real delegated work cycle: YES.**

Task t-001 — added an optional `min_cost` filter to `tools/
usage_report.py`'s `build_report()` (and a `--min-cost` CLI flag) —
was specced by the coordinating session, implemented by a builder-tier
(sonnet) subagent with a real pytest witness (312 passed), reviewed by a
critic-tier (opus) subagent (mandatory here since the coordinator ran at
the same tier as the builder, so no skip waiver was available), verdict
ACCEPT, and committed.

## FINAL STATE

**Files created/modified (beyond the template's own shipped files):**
- `PROCESS/SCOUT_GOLDEN_SET.md` (new — generated golden set + run log)
- `PROCESS/CRITIC_EXAM.md` (new — seeded diff, key, two attempt logs)
- `PROCESS/LEAD_RANKING_EXAM.md` (appended — run #1 log entry)
- `logs/routing-log.jsonl` (seed line fixed + 3 appended events)
- `tools/usage_report.py`, `tools/test_usage_report.py` (t-001 diff)
- `STRANGER_REPORT.md` (this file)

**Routing journal (`logs/routing-log.jsonl`), verbatim:**

```
{"ts":"2026-07-11T19:23:56","event":"journal_created","agent":"system","category":"meta","notes":"journal initialized by onboarding"}
{"ts":"2026-07-11T21:40:08","event":"calibrated","agent":"lead","model":"claude-fable-5","category":"evaluation","notes":"onboarding entrance exam: PROCESS/LEAD_RANKING_EXAM.md, candidate claude-fable-5, chief judge claude-opus-4-8 (deviation: no tier above fable exists under a subscription-only contour; opus used as best-available judge), score 12/12, PASS"}
{"ts":"2026-07-11T21:44:12","event":"delegated","agent":"builder","model":"claude-sonnet-5","task_id":"t-001","category":"implementation","notes":"spec: add optional min_cost filter (>=) to tools/usage_report.py build_report()'s top_sessions_by_cost, plus --min-cost CLI flag, backward compatible (default None); DoD: new test in tools/test_usage_report.py, canonical pytest run as witness"}
{"ts":"2026-07-11T21:46:44","event":"accepted","agent":"builder","model":"claude-sonnet-5","task_id":"t-001","category":"implementation","by":"opus","witness":"python -m pytest tools/ gateway/ -q -> 312 passed in 33.58s (builder's own run: 312 passed in 33.88s); critic independently reran the full suite plus -k min_cost (1 passed) and confirmed the filter logic, backward-compat default, and no SIBLING_MAP axis affected","notes":"critic review mandatory here (coordinator=claude-sonnet-5 is same tier as builder=claude-sonnet-5, so the critic:skipped waiver is unavailable per the role-vs-tier acceptance matrix); critic verdict ACCEPT, no blocking findings; Lead accepts"}
```

**Git log of this project:**

```
f64e34d 2026-07-11 21:47:29 +0200 Add --min-cost filter to usage_report.py's top-sessions table
92a21e7 2026-07-11 21:40:59 +0200 Onboarding: entrance exams for scout, critic, and lead
8bfb8d2 2026-07-11 21:25:17 +0200 Install Supervised Delegation template
```
