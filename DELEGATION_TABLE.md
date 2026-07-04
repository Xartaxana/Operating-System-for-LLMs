# Delegation Table

A living document. Every row starts as an estimate and is refined by
Shadow Evaluation during implementation (see ARCHITECTURE.md, D-0028).

Status values:

- `estimated` — expert guess, not yet measured;
- `validated` — confirmed by Shadow Evaluation on real requests;
- `rejected` — delegation attempted and found harmful.

Cost = typical Lead token spend on this task type.
Value = how much frontier intelligence actually improves the result.

| Task type | Cost (Lead) | Value of Lead | Delegate to | Status |
|---|---|---|---|---|
| Strategic planning, architecture | High | Very high | Lead only | estimated |
| Research, hard debugging | High | Very high | Lead only | estimated |
| Idea generation | Medium | High | Lead, cheap model for expansion | estimated |
| Routine code generation | High | Medium | Middle | validated |
| Summarization | Medium | Medium | Junior | validated |
| Re-explaining known context | High | Low | eliminate via context compression | estimated |
| Checking lists, verification passes | Medium | Low | Junior | estimated |
| Data extraction, JSON conversion | Medium | Low | Intern | validated |
| Formatting (Markdown, tables) | Low–Medium | Low | Intern | validated |
| Classification, tagging | Low | Low | Junior | rejected |
| Duplicate / repetition detection | Low | Medium | Ledger (no LLM) | estimated |
| Token and cost accounting | — | — | Guard/Ledger (no LLM) | estimated |

## Update Rules

1. A row may change status only with evidence attached
   (Shadow Evaluation sample or production incident).
2. New task types are added as they appear in the Ledger.
3. "Re-explaining known context" is tracked as the primary suspected
   cost driver; its row is retired when context compression ships.
4. Shadow Evaluation compares TOTAL task cost (including retry loops),
   not per-request cost: external data shows a cheaper model can need
   10 loops where a frontier model needs 1, erasing the price advantage
   (see docs/RELATED_WORK.md, "Tokenomics in Action").

## External Evidence (priors, not measurements)

Figures from outside sources that our own telemetry should confirm or
refute. Sources and details: docs/RELATED_WORK.md.

| Claim | Figure | Source |
|---|---|---|
| Re-sent conversation history share of token spend | 50–62% | Unblocked, 2026 |
| Input tokens share of agentic session cost | ~85% (input:output ≈ 25:1) | Vantage, 2026 |
| Tokens wasted on redundant context / re-reading | 30–40% | arXiv:2604.22750 |
| Savings from summarization + budget-aware planning | 25–35% | arXiv:2604.22750 |
| Cascade routing cost reduction at equal quality | up to 98% (benchmarks) | FrugalGPT |
| GPT-4-class quality with 26% of frontier calls | 95% quality | RouteLLM |
| Prompt-cache discount on cached prefix | ~90% | provider pricing |
| Frontier vs cheap model retry loops on same task | 1 vs 10 loops | Klyshevich, 2026 |

## Shadow Evaluation Log

Evidence for Update Rule 1. One line per Shadow Evaluation run.

Caveat on cost_target=$0.0000 (2026-07-04, Rule #1 cost accounting
fix): every evidence line below dated <= 2026-07-03 shows
cost_target=$0.0000 as a CLIENT-SIDE ACCOUNTING ARTIFACT, not an
actual $0 — shadow_eval.py was pricing the gateway alias name
(e.g. "openai/middle-groq") against litellm's own client pricing
map, which doesn't know gateway aliases, so completion_cost()
silently raised and was swallowed. The proxy-side accounting in
gateway/requests.db was correct throughout. Fixed by reading
response._hidden_params["response_cost"] (falls back to the
requests.db row when absent); judge cost is now captured the same
way and shown as judge_cost=$X.XXXX. Runs from 2026-07-04 onward
show honest nonzero costs.

Caveat on the comparison method (2026-07-03): sim is difflib
character-level similarity. High-sim `validated` verdicts are
trustworthy; low-sim `rejected` verdicts are SUSPECT — a verbose
answer scores near zero against a terse one even when semantically
identical. Confirmed by manual review the same day (see below):
2 of 5 difflib verdicts were wrong for exactly this reason.

- 2026-07-03  category=coding  source=lead-gemini target=intern  n=2  sim=0.10  cost_source=$0.0044 cost_target=$0.0000  -> rejected
- 2026-07-03  category=summarization  source=lead-gemini target=intern  n=2  sim=0.52  cost_source=$0.0016 cost_target=$0.0000  -> validated
- 2026-07-03  category=extraction  source=lead-gemini target=intern  n=2  sim=0.91  cost_source=$0.0003 cost_target=$0.0000  -> validated
- 2026-07-03  category=classification  source=lead-gemini target=intern  n=2  sim=0.04  cost_source=$0.0021 cost_target=$0.0000  -> rejected
- 2026-07-03  category=formatting  source=lead-gemini target=intern  n=2  sim=0.60  cost_source=$0.0004 cost_target=$0.0000  -> validated

Manual semantic review of the same 11 pairs (judge: Claude Fable 5,
2026-07-03; full labeled pairs in gateway/judge_calibration.json —
the calibration set the automated LLM judge must reproduce):

- coding: difflib rejected -> OVERTURNED to validated. Both intern
  answers are correct (s[::-1]; iterative two-variable loop); low sim
  measured verbosity, not quality. Caveat: one-shot quality, n=2 —
  retry-loop cost (Update Rule 4) still unmeasured.
- classification: rejected CONFIRMED, but for the right reason now:
  in 1 of 2 pairs intern gave a defensible-looking but flawed verdict
  (negative vs neutral, misreading what "but" emphasizes). Not a
  difflib artifact — a genuine quality gap.
- summarization, extraction, formatting: validated CONFIRMED;
  differences are cosmetic (verbosity, code fences, preambles).
RETRACTED (2026-07-03, chief-judge review): the four lines below are
contaminated. A failed lead-gemini calibration attempt logged its
judge prompts as regular lead-gemini traffic, and this run's random
sample included 6 nested judge prompts out of 11 pairs, inflating n.
The 5 clean pairs in the run all received correct judge verdicts
(manually confirmed), so no table Status was changed by retraction.
Sampling now excludes judge calls; clean rerun follows.

- 2026-07-03  category=coding  source=lead-gemini target=intern  n=4  sim=0.51  judge=middle-groq pass_rate=1.00  cost_source=$0.0023 cost_target=$0.0000  -> validated [RETRACTED]
- 2026-07-03  category=summarization  source=lead-gemini target=intern  n=4  sim=0.55  judge=middle-groq pass_rate=1.00  cost_source=$0.0013 cost_target=$0.0000  -> validated [RETRACTED]
- 2026-07-03  category=extraction  source=lead-gemini target=intern  n=1  sim=0.84  judge=middle-groq pass_rate=1.00  cost_source=$0.0003 cost_target=$0.0000  -> estimated [RETRACTED]
- 2026-07-03  category=formatting  source=lead-gemini target=intern  n=2  sim=0.98  judge=middle-groq pass_rate=1.00  cost_source=$0.0005 cost_target=$0.0000  -> validated [RETRACTED]
Clean rerun (2026-07-03, judge-call contamination filter active; all
11 sampled pairs verified clean by chief-judge review):

- 2026-07-03  category=coding  source=lead-gemini target=intern  n=2  sim=0.08  judge=middle-groq pass_rate=0.50  cost_source=$0.0044 cost_target=$0.0000  -> rejected [OVERRULED, see below]
- 2026-07-03  category=summarization  source=lead-gemini target=intern  n=2  sim=0.46  judge=middle-groq pass_rate=1.00  cost_source=$0.0016 cost_target=$0.0000  -> validated
- 2026-07-03  category=extraction  source=lead-gemini target=intern  n=2  sim=0.87  judge=middle-groq pass_rate=1.00  cost_source=$0.0003 cost_target=$0.0000  -> validated
- 2026-07-03  category=classification  source=lead-gemini target=intern  n=2  sim=0.02  judge=middle-groq pass_rate=0.50  cost_source=$0.0021 cost_target=$0.0000  -> rejected
- 2026-07-03  category=formatting  source=lead-gemini target=intern  n=2  sim=0.62  judge=middle-groq pass_rate=1.00  cost_source=$0.0004 cost_target=$0.0000  -> validated

Chief-judge ruling on coding (2026-07-03): rejected OVERRULED, row
stays validated. The judge's WORSE is the same systematic strictness
call it made in calibration (mismatch #2): it penalizes the fibonacci
answer for missing negative-n input validation that the task never
asked for. The fresh intern replay was manually verified correct
(two-variable iterative loop, correct n=0/1/2 walkthrough). This is
the judge's one known bias — consistent across two independent runs —
and should be addressed by tuning JUDGE_SYSTEM_PROMPT ("only
correctness w.r.t. what the task asked"), not by accepting the
verdict. classification rejected STANDS: the judge's WORSE there
matches the manual review (intern's flawed sentiment reasoning).

- 2026-07-03  category=coding  source=lead-gemini target=middle-groq  n=2  sim=0.25  judge=judge-groq pass_rate=1.00  cost_source=$0.0044 cost_target=$0.0000  -> validated

First run where the target IS the tier the row names (coding ->
Middle; earlier evidence used intern as a stand-in). Run restricted
via --categories coding so other rows are not updated from a target
that does not match their Delegate-to tier. Chief-judge review of
both pairs (2026-07-03): reverse_string and fibonacci replays are
correct code with docstrings; both EQUIVALENT verdicts confirmed.
Row stays validated, now with tier-matching evidence.

Judge upgraded (2026-07-03, follow-up): the "strictness" diagnosis
above was wrong — when asked to explain, middle-groq hallucinated a
bug while tracing the correct loop (claimed the code returns b; it
returns a). Prompt tuning did not flip it. Default judge replaced:
judge-groq (groq/openai/gpt-oss-120b, reasoning model, same free
key), calibration 11/11 including the fibonacci pair. Future runs
use judge=judge-groq; middle-groq remains a replay TARGET only.
