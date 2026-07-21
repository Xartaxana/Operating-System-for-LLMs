# Architecture — Boot Core (D-0067)

The session-sized operative core of the architecture. The
authoritative FULL specification — diagrams, component details,
portability, rationale — is ARCHITECTURE.md, point-read on demand.
Editing a section of the full spec? Check whether this core must
follow (SIBLING_MAP axis 4 pair; the full spec's header carries the
same duty in the other direction).

## Problem

The Lead (strongest model) burns budget on work that does not
require frontier intelligence. The system keeps the Lead on hard
problems while cheaper components enforce budgets, explain spending,
and take over delegable work.

## Core Insight

"A junior model watching the senior model" decomposes into three
mechanisms with different reliability requirements:

1. **Enforcing limits** — 100% reliability, zero latency:
   deterministic software, never an LLM.
2. **Explaining where tokens go** — analytics over a request log;
   an LLM is only needed to narrate results.
3. **Recommending delegation** — the only genuine LLM task, and even
   it is validated against real data (Shadow Evaluation on the API
   contour, the routing journal on the subscription contour).

**Rule #1: the cost of supervision must be measurably lower than the
savings it produces. A component that violates this rule is removed.**

**Two-layer enforcement (D-0063): code guarantees the ENCOUNTER with
a rule; AI judges the meaning.** A gate on the execution path cannot
be skipped, but decides only the deterministically decidable
(presence, shape, typed fields, counts). The verdict on fulfillment
IN MEANING belongs to an AI tier above the performer — acceptance,
critic, calibration — and is never inferred from syntactic proxies.
The inverse holds too: a deterministically decidable sub-question
must not live on AI attention (it drifts and it costs, Rule #1).
Discipline-held mechanisms are promoted to gates on journal evidence
of leaks, never for symmetry.

## One Architecture: Two Task Paths, Two Supply Channels (D-0034 → D-0088)

- **The task's path is single and chosen by SIZE at intake, not by
  contour** (D-0087/D-0088): LEAF (one performer, one
  allocate-category, no dependencies; doubt = graph) → allocate
  ladder → worker → calibrated-judge acceptance (`basis: "judge"`) →
  R6 mirror. GRAPH → Lead DAG + per-node keys → each leaf node runs
  the same leaf machinery → Lead integration + critic gate; questions
  go UP (D-0077).
- **"Contours" are supply-and-measurement CHANNELS, not
  architectures** (deployment bindings, D-0062): subscription channel
  (subagents + subscription judge, 13/13 equivalence t-254) and API
  channel (gateway aliases + gateway judge — the only channel for
  script-driven constructions and replay). What did not collapse:
  replay/Shadow Evaluation exists only on the API channel; accounting
  stays two-source (cc_usage vs requests.db, one Ledger); judge
  calibration (D-0031) lives on the gateway.
- Identical everywhere: Rule #1; accounting prices (D-0032 —
  subscription usage at API list prices, free tiers are cash
  discounts, not zero cost); evidence-gated statuses in
  DELEGATION_TABLE.md (4-state, D-0035); judge supervision.
- Delegation is FLAT (D-0037): workers never spawn workers;
  decomposition, specs and graph-acceptance stay with the
  coordinator. Workers run in the background by default (D-0040).
- Nothing in the running system is a routing component: the
  auto-loaded policy (CLAUDE.md) IS the router; porting the system
  means porting a POLICY, not software (D-0005, D-0062).

## On-demand map — point-read ARCHITECTURE.md for:

- **Portability (the policy is the router)** — the four requirements
  a new deployment must supply; three deployment targets and their
  validation status.
- **Two Vocabularies: Functions and Grades** — the D-0062 bridge
  table (functions scout/builder/critic/Lead vs grades
  intern/junior/middle/senior) and its consequences.
- **Components (API contour)** — Gateway / Guard / Ledger / Analyst
  / deferred Router details, both mermaid diagrams.
- **Shadow Evaluation** — replay mechanics; contour asymmetry and
  the regression bridge (how journal evidence feeds API-contour
  regression replays).
- **Deliberately Deferred / MVP Stack** — what is NOT built and why.

Phases and gates live in ROADMAP.md (single owner). Plan of record:
docs/UNIFIED_PLAN_2026-07-07.md. Delegation evidence:
DELEGATION_TABLE.md (statuses) + docs/SHADOW_EVALUATION_LOG.md
(run log, D-0067).
