# Shadow Evaluation First Runs and LLM Judge (2026-07-03..04)

Archived verbatim from CURRENT_CONTEXT.md on 2026-07-07 (D-0038).
Status at archive time: complete. Live summary: judge-groq
(gpt-oss-120b) is the default judge, calibrated 13/13 at
temperature=0; protocol in PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
(D-0031); evidence lines in DELEGATION_TABLE.md.

---

## Phase 1 step 5: Shadow Evaluation (original objective text)

Phase 1 step 5: Shadow Evaluation. gateway/shadow_eval.py is built and
tested (11 passing tests, no live model needed — mock_response like
test_analyst.py): samples successful requests for --source-model,
replays them on --target-model, compares via difflib similarity
(transparent heuristic, LLM judge deferred), aggregates by the same
task category metrics.py uses, and (--update-table) writes
validated/rejected verdicts into DELEGATION_TABLE.md + an evidence
log entry. Guards: refuses source==target (self-comparison is not
delegation evidence); a category stays "estimated" (inconclusive)
below --min-samples (default 2).

First real run completed 2026-07-03. Gemini free tier connected:
alias `lead-gemini` (gemini/gemini-2.5-flash; 2.0-flash has ZERO
free-tier quota on this key — 429, don't use it). Key lives in
gitignored gateway/.env; litellm did NOT auto-load it, export the
variable before starting the proxy. 10-request working set (2 per
category) replayed on `intern`; DELEGATION_TABLE.md now has its first
evidence-backed verdicts + a "Shadow Evaluation Log" section:
extraction 91% / formatting 60% / summarization 52% -> validated;
coding 10% / classification 4% -> rejected.

---

# Completed 2026-07-03: LLM Judge (built, calibrated, protocolized)

LLM judge DONE (2026-07-03). shadow_eval.py gained --judge-model
(judge through the gateway; verdicts override difflib in
decide_status via pass_rate >= --pass-threshold, default 0.75),
--calibrate (agreement report against judge_calibration.json), and
per-pair verdict logging. 31 tests pass.

Calibration history: middle-groq (Llama-3.3-70B via Groq free tier)
agreed 10/11 and was adopted 2026-07-03, then REPLACED the same day —
see below. lead-gemini as judge is impractical: free tier is 5
req/min (verified 429) and it would judge its own source answers
(self-preference bias). analyst (4B) not evaluated — no need while
Groq is free.

JUDGE UPGRADE (2026-07-03, later session): the fibonacci miss was NOT
strictness — diagnosis (asking the judge to explain) showed
Llama-3.3-70B hallucinates a bug while "tracing" the correct
`a, b = b, a + b` loop (claims the code returns b; it returns a).
Prompt hardening (judge only the explicit task; step-by-step check
before claiming a bug) did not flip it — a capability ceiling, not a
prompt problem. The hardened prompt was kept, and the judge was
upgraded: alias `judge-groq` = groq/openai/gpt-oss-120b (reasoning
model, same free Groq key), screened directly against the calibration
set (gpt-oss-120b 11/11; qwen3-32b 7/11 with rate-limit errors and a
real miss on pair #7), then officially calibrated through the gateway:
11/11. ADOPTED as default judge. judge-groq is a role alias (never a
traffic source), so judge cost stays separable in the Ledger and the
contamination filter has a second line of defense.

Judged runs done (2026-07-03), with two process lessons the hard way:

1. CONTAMINATION: the first judged run sampled 6/11 nested judge
   prompts — the failed lead-gemini calibration had logged its judge
   calls as regular lead-gemini traffic. Caught only because the
   Architect asked whether the chief judge (Claude) had reviewed the
   run. Fixed: sample_requests() excludes judge calls (prompt LIKE
   filter + test); contaminated log lines marked [RETRACTED].
2. JUDGE BIAS — RESOLVED (2026-07-03): root cause was middle-groq
   mis-tracing correct code, not strictness (see JUDGE UPGRADE above).
   Judge replaced with judge-groq (gpt-oss-120b), calibration 11/11.
   Lesson: when a judge misses, ask it to explain before tuning the
   prompt — the stated theory ("penalizes missing validation") was
   wrong, and two prompt fixes aimed at it changed nothing.

Process rule going forward: judge verdicts that CHANGE a table status
get a chief-judge (or Architect) review of the actual pairs before
the change is accepted; --update-table output is not self-certifying.
Extended 2026-07-03 into PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
(D-0031): reviews grow judge_calibration.json, 1-2 random verdicts
audited per run, recalibration every ~5 new pairs, judge model
upgraded only on measured agreement drop below 90%.

Protocol applied same day: the two chief-judge-reviewed pairs from
the coding->middle-groq run appended to judge_calibration.json (now
13 pairs). First recalibration exposed verdict nondeterminism at
default temperature (borderline pair #7 flipped between runs:
11/11 -> 12/13); judge_pair now defaults to temperature=0.
Current baseline: judge-groq 13/13, reproduced twice.

Local-judge fallback measured (2026-07-04): Qwen3-4B (alias analyst,
GTX 1060) scored 11/13 (84.6%) on the calibration set — below the
90% protocol bar. Its two misses are exactly the discriminating
pairs: #2 fibonacci (code tracing — same failure mode as
Llama-3.3-70B) and #7 borderline sentiment. Judge capability tracks
the model hierarchy: 4B fails both hard pairs, 70B fails code
tracing, 120B reasoning passes all 13. Conclusion: no local judge on
this hardware; revisit only if the Groq free tier disappears
(fallback order: judge-groq > paid API judge > local 4B with
category restrictions). Caveat: Ollama default context window may
truncate the longest pairs — untested, could only improve the 4B.

DONE (2026-07-03): "Routine code generation -> Middle" tested with
middle-groq as TARGET, judge-groq as judge: n=2, pass_rate=1.00,
chief-judge review confirmed both pairs -> row validated with
tier-matching evidence (earlier evidence used intern as a stand-in).
shadow_eval.py gained --categories (whitelist) so a run aimed at one
row cannot update rows whose Delegate-to tier differs from the
target. 33 tests pass.

Next: (a) grow real traffic volume (n=2 per category is thin);
(b) once ANTHROPIC_API_KEY exists, repeat against the true paid Lead.
