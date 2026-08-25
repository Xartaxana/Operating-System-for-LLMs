# Engineering Process

This directory contains the engineering protocols that define how the project evolves.

The project must not depend on any individual LLM remembering the workflow.

The repository stores both project knowledge and engineering processes.

## Protocols

- BOOT_REPORT_PROTOCOL.md
- DOCUMENTATION_PROTOCOL.md
- JUDGE_CALIBRATION_PROTOCOL.md
- PATCH_PROTOCOL.md
- PRE_COMMIT_PROTOCOL.md
- SESSION_PROTOCOL.md
- WEEKLY_CALIBRATION_PROTOCOL.md — weekly calibration
- ZERO_CONTEXT_PROTOCOL.md

## Exams (tier entrance/regression sets)

- CRITIC_EXAM.md — critic's exam (generated at onboarding; not present
  on a fresh kit tree until the material threshold below is met)
- SCOUT_GOLDEN_SET.md — scout's golden set (generated at onboarding;
  same threshold)
- LEAD_RANKING_EXAM.md — Lead ranking
- DEPLOYMENT_ECONOMY_EXAM.md — deployment economics

### Delivery form of an exam into a host deployment — the rule

An asymmetry exists between these four sets: LEAD_RANKING and
DEPLOYMENT_ECONOMY ship as CONTENT (this file, as-is); critic and scout
ship as GENERATORS (skills that build the set fresh from the host's own
tree, `.claude/skills/critic-exam-gen`, `scout-exam-gen`, where those
skills exist in a given kit copy). The rule that explains the asymmetry
and makes it reproducible:

**Delivery form follows the set's DEPENDENCE ON MATERIAL.**
- A set whose tasks are nailed to OUR OWN tree (defects seeded into our
  own files, golden questions about our own repository, a real
  canonical test count) ships as a GENERATOR. Shipped as content, it
  would be green by construction on a foreign host and measure
  nothing — the delivery would look like it happened while no check
  actually ran.
- A set whose tasks are SELF-CONTAINED (judgment calls about the tier
  ladder, deployment-economics scenarios — synthetic, not tied to a
  tree) ships as CONTENT: a generator would add nothing here.

The criterion is one question to the set: "shipped as-is to a foreign
host, does it stay green regardless of what's inside that host?" Yes —
a generator is needed.

### Empty project: the exam is deferred until material exists

The fork "what to do when the host has no material at all" is closed by
a threshold, not a cancellation or a placeholder substitute: **too
little material → the exam is deferred, not cancelled and not faked.**

The key part of the form: it needs no new machinery. An adoption ledger
already carries a `deferred(<trigger>)` status and the rule "a
mechanism installed with no prerequisite is forbidden by construction —
a missing prerequisite routes the row into `deferred(<trigger>)`, never
a bare `adopt`." The entrance exam simply gets the prerequisite it did
not have:

**The entrance exam's prerequisite is MATERIAL**, and it does not
reduce to a file count, because a set is built from three DIFFERENT
kinds of material:
1. **A runnable test suite with a stable count.** Without it, the
   fabricated-witness trap cannot be built — it needs a real canonical
   count to check the claimed witness against.
2. **Kin — at least two files of the same kind.** Without it, a
   class-completeness gap cannot be seeded — there is nothing to leave
   uncovered.
3. **Files to seed a diff into, and to ask the scout about.** A
   starting threshold of **20 source files** beyond the kit itself.
   This is a PRIOR, not a measurement: the first host that crosses it
   is the basis for refining the number.

While any of the three is missing, the exam's ledger row reads
`deferred(material: <which of the three is missing>)`. The tier still
works, just UNEXAMINED, and that is the cost of the decision; the
mitigation is visibility — the `deferred` row is shown at every session
start, so the operator knows the state rather than forgetting it.

**DETECTOR (mechanism rule (d)) — RE-ARMING.** A deferred exam with no
detector turns into a silent, permanent exemption, which is worse than
a cancellation: a cancellation is visible, a silent deferral is not.
Detector: the host's own onboarding-wiring check, which already reads
the ledger, is obligated to re-read `deferred` rows and warn when the
trigger condition has become true — material appeared, the exam has not
run.

HONEST ABOUT STATE: this re-arming is NOT wired into this kit's own
wiring check as of this port. The rule ships to a host ONLY in the same
batch as that re-arming; until that batch exists, the rule lives as a
decision on the source deployment's side and is not shipped further —
a mechanism with no working detector is a wish, and shipping it as a
delivery would pass off a wish as a check.
