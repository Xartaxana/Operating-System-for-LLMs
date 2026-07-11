# Toolkit Stage 5a — Stranger-Session Prompt (t-055)

The exact prompt handed to the independent "stranger" session that
validates the toolkit's onboarding on an EMPTY project (actual
polygon: D:\Improving_AI\From_Zero, launched by the operator
2026-07-11). Kept in the repo per D-0014 (no important knowledge
only in chat); reusable for stage 5б and future re-validations.

---

You are a developer adopting a delegation toolkit into this brand-new EMPTY project (current directory; git is already initialized, nothing else exists).

The toolkit: https://github.com/Xartaxana/Supervised-Delegation

Your setup, as a user: you work in Claude Code on a subscription; Haiku / Sonnet / Opus models are available to you as subagents; you have NO API keys and do not want to configure any external gateway today.

Act exactly as a careful first-time user:

1. Start from the repository's README on GitHub (fetch/clone as its own docs direct). Follow README -> INSTALL -> onboarding AS WRITTEN, step by step, in order.
2. When the docs offer a choice, pick what fits the setup above. When the docs are ambiguous or contradictory, record it verbatim (file + quote), choose the most reasonable reading, and continue.
3. Proceed all the way to the FIRST REAL DELEGATED WORK CYCLE — dispatch a worker per the installed policy and accept its result per the installed rules — if the docs get you there. Invent a small realistic task for that cycle if the docs ask you to supply one.
4. STRICT RULES: the toolkit's own files are your ONLY source of instructions. Never silently invent a missing step — every invention is a stumble to record. Stay inside this project directory (cloning the toolkit repo into a subdirectory or wherever its docs specify is fine).

DELIVERABLE — a structured report (save it as STRANGER_REPORT.md in the project root when done):
- STEP LOG: what you did, in order, each step tagged with the doc file/section that told you to do it;
- STUMBLES (the most important part): every place you tripped — ambiguity, contradiction, missing file, broken command, dead link, instruction that does not match reality, a question the docs could not answer — each entry: file path + verbatim quote + what happened + what you did about it;
- OUTCOME: reached the first delegated cycle yes/no; if no — the exact blocker;
- FINAL STATE: files created, the routing journal's contents verbatim, git log of this project.
