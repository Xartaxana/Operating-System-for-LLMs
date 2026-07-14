# Judge Calibration Protocol

Привязка: D-0031 (ретро-свип rule-10 2026-07-11).

## Purpose

Shadow Evaluation verdicts are only as trustworthy as the LLM judge
producing them. The judge is itself a delegated worker and is
supervised the same way the architecture supervises everything else:
a cheap model does the routine work, the Lead escalates on evidence
(ARCHITECTURE.md Rule #1: supervision must cost less than the savings
it produces).

Origin (2026-07-03): the first judge (middle-groq, Llama-3.3-70B)
passed 10/11 calibration and was adopted; its one miss was
misdiagnosed as strictness. Asking the judge to explain revealed it
hallucinated a bug while tracing correct code. Prompt tuning did not
help; the judge was replaced (judge-groq, gpt-oss-120b, 11/11). A
point-in-time calibration on a small synthetic set is a snapshot,
not a guarantee.

## Roles

- **Judge** — the gateway alias passed to `shadow_eval.py
  --judge-model` (currently `judge-groq`). Rules on every replayed
  pair.
- **Chief judge** — the Lead-tier model working on the repository
  (or the Architect). Rules only on escalations and audits.

## Rules

1. **Status changes require review.** A judge verdict that CHANGES a
   DELEGATION_TABLE.md row status is accepted only after the chief
   judge (or the Architect) reviews the actual pairs.
   `--record-evidence` output is not self-certifying (the flag only
   appends evidence lines; no code path writes table statuses, t-095).

2. **Reviews grow the calibration set.** Every pair the chief judge
   reviews (rule 1 or rule 3) is appended to
   `gateway/judge_calibration.json` with the chief judge's label and
   rationale. The set thereby tracks the real traffic distribution
   instead of staying a synthetic snapshot.

3. **Random audit per run.** On every Shadow Evaluation run, the
   chief judge reviews 1–2 randomly chosen verdicts even when no
   status changed. Quiet wrong verdicts never surface otherwise
   (the sampling-contamination incident was caught only because the
   Architect happened to ask).

4. **Recalibrate on growth.** After every ~5 pairs added to the
   calibration set, re-run
   `python shadow_eval.py --calibrate judge_calibration.json
   --judge-model judge-groq` and record the agreement in
   CURRENT_CONTEXT.md.

5. **Escalate on evidence, not anxiety.** If agreement on the full
   set drops below 90%, diagnose before tuning: ask the judge to
   explain its mismatched verdicts (one-off diagnostic prompt, not
   the production prompt). Only then decide between prompt fix and
   model upgrade. A stronger default judge is adopted only with a
   measured failure in hand, per Measure Before Optimizing.

6. **Judge is never a traffic source.** The judge alias must not be
   used as `--source-model`; `sample_requests()` additionally filters
   judge prompts by their first sentence (keep that sentence stable
   when editing JUDGE_SYSTEM_PROMPT).

7. **A new measuring instrument is calibrated with a known-tier
   control run before its verdicts are used** (F-30 layer 6). Any new
   judge, golden set, exam or metric first runs on a candidate whose
   tier is already known; saturation by a lower-tier control means
   the instrument does not discriminate at the top (precedents: the
   Lead exam saturated by Sonnet, F-28; the ranking exam's
   pre-registered gap threshold firing on its first run, t-028).
   The instrument's own failure detector stays rule 10(в)-mandatory.
