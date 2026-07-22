# Supervised Delegation: an Operating System Approach to LLM Cost

**White Paper — living draft v0.2.2 (2026-07-22)**

Status: draft. Every claim in section 7 is backed by repository
evidence (commits, DELEGATION_TABLE.md + docs/SHADOW_EVALUATION_LOG.md,
requests.db, logs/routing-log.jsonl, docs/FINDINGS.md); numbers
will be revised as telemetry volume grows. Deliverable #1 of
PROJECT_CHARTER.md.

Changelog: v0.2.2 (2026-07-22) — §4.3 extended with the delivery
upgrade layer (D-0091: versioned ledgers, revision-delta
re-inventory, role files as diffable delivery content — the F-52
lesson; D-0092: an adopt row is a wiring commitment); §5 calibration
check count refreshed (33), §10 roadmap updated (judge-acceptance
window collected 07-22, toolkit v0.5.0 assembled and gated behind
calibration #4), §11 limitations re-aged.
v0.2.1 (2026-07-13) — evidence update after the first
full production-evidence cycle. First weekly calibration moved the
four Claude-contour rows to provisionally_validated (§5, §5.1, §7);
Phases 1/1.5 closed; Phase 3 (toolkit, D-0070..D-0074) executed and
released as a public template validated by two independent installs
— the §4.1 portability claim demonstrated, not argued. A paid Lead
entered production through the gateway (API window), giving the API
contour its first real traffic and the sharpest reversal so far:
four consecutive paid-source reject runs against the
coding→Middle row, plus the finding that on micro-tasks the paid
frontier source was cheaper than the delegation (§5, §7). The
Phase 2 gate report was signed 2026-07-13: context-management
workstream CLOSED by direct cache-aware measurement (paid uncached
input 0.11% vs the 25% threshold), task-pipeline workstream OPENED
(carrier evaluation done, markdown DAG artifact piloted), Router
still red (§10). Measurement honesty hardened into construction
(D-0075, F-37/F-38 — §6.2); boot diet round 5 cut the policy text
itself behind its code gates, verified by critic + golden set (§8).
v0.2.0 (2026-07-10) — full-document revision against the
decision index (now D-0068) and the live evidence streams, folding in
everything since v0.1: the deployed routing MVP with its typed
journal and acceptance matrix (§5.1; D-0052..D-0058, D-0060), the
two-vocabularies bridge (§4.1, D-0062), the 4-state status model in
§5 (D-0035, queued since v0.1.1), the second judge and the
instrument-saturation finding with ranking-exam evidence (§6, F-28),
a new §6.2 — the coordinator as a supervised worker (F-27/F-29/F-30,
two-layer enforcement D-0063, degradation protocol), a refreshed
empirical table (§7: subscription baseline, cache dominance,
local-scout rejection, exam results), boot-budget economics and
session symmetry (§8; D-0050, D-0067/68), positioning vs adjacent
harnesses (§9, D-0066), Phase 1.5 and the third Phase-2 gate in the
roadmap (§10, D-0059), and updated limitations (§11). Supersedes the
v0.1.x text under Architect review. v0.1.2 (2026-07-09) — §4.1 and
§5.1 added. v0.1.1 (2026-07-07) — §4 diagram replaced with the full
target scheme per the first Architect review comment.

---

## 1. Abstract

Frontier LLMs spend a large share of their budget on work that does
not require frontier intelligence: re-explaining context, formatting,
extraction, routine code. The obvious fix — "let a junior model watch
the senior model" — fails as stated, because supervision itself has a
cost and a reliability profile. This paper describes an architecture
that decomposes supervision into three mechanisms with different
reliability requirements (deterministic enforcement, deterministic
analytics, LLM recommendation), binds them with one economic rule —
supervision must cost measurably less than the savings it produces —
and validates every delegation decision with evidence instead of
intuition — on two contours. The API contour is a lab: a gateway, a
SQLite log, pure-Python metrics, one local model, and an offline
replay harness with a supervised LLM judge. The production contour
has no routing software at all: an auto-loaded policy file IS the
router, executed by the coordinator session itself, and validated
in production by a typed dispatch journal — so porting the system
means porting a policy, not code. Its development process is part
of the claim: the project is built by the same hierarchy it
describes, with the repository serving as the system's persistent
memory — including evidence that the coordinator itself is the
component most in need of supervision.

## 2. Problem

The strongest available model (the **Lead**) consumes tokens faster
than any smaller model, does not notice when limits approach, and
external measurements suggest most of its spend is not intelligence
but repetition: 50–62% of token spend in agentic coding sessions is
re-sent conversation history, and 30–40% of tokens are redundant
context re-reading (docs/RELATED_WORK.md). Input tokens dominate
session cost (~85%, input:output ≈ 25:1). Our own first baseline
(§7) adds a caution to those priors: on the subscription contour
97.6% of input-side tokens were already served from provider cache —
repetition is real, but most of it is already discounted ~90% at the
provider, so the actionable metric is PAID UNCACHED re-sent input,
not raw repetition (D-0036). The direct measurement followed on
2026-07-13, on paid interactive traffic routed through our own
gateway: truly uncached paid input was 0.11% of the input side
against a 25% gate threshold — the external 50–62% prior describes
raw repetition honestly, and provider caching has already taken that
money off the table (§7, §10).

Meanwhile, the naive cost fix — replace the frontier model with a
cheaper one — can backfire end-to-end: production data shows an
identical task taking a frontier model 1 attempt, a mid-tier model
3–5, and a small model 10, erasing the per-token price advantage.

The context cost itself has two distinct layers that require
different fixes:

- **Intra-session:** LLM APIs are stateless, so an agent re-sends the
  entire message history on every call and is re-billed for it as
  input; naive agent loops are quadratic in step count. This layer is
  addressed by context compression (§10) — a mature external tooling
  landscape our system validates rather than reinvents.
- **Inter-session:** each new session starts blank and must re-learn
  project state, either by dragging an ever-growing conversation or
  by a human re-explaining. This layer is addressed by the repository
  as persistent memory (§8).

So the problem is not "use cheaper models". It is: **keep the Lead on
work that needs it, prove which work does not, and make sure the
proving machinery costs less than it saves.**

## 3. Core Insight: Supervision Decomposes

"A junior model watching the senior model" is three different jobs
with incompatible reliability requirements:

1. **Enforcing limits** requires 100% reliability and zero latency.
   This is deterministic software in the request path — never an LLM.
2. **Explaining where tokens go** is analytics over a request log.
   The math is deterministic; an LLM is only needed to narrate.
3. **Recommending delegation** is the only genuine LLM task — and
   even it must be validated against replayed real traffic before it
   changes anything.

**Rule #1: the cost of supervision must be measurably lower than the
savings it produces. A component that violates this rule is removed.**

Everything else in the architecture is a consequence of this
decomposition.

## 4. Architecture

```mermaid
flowchart TB
    USER([User])

    subgraph path["Request path — synchronous, deterministic"]
        GW["Gateway — LiteLLM proxy<br/>single interception point"]
        GUARD["Guard — budget counters, no LLM<br/>80% warn / 100% cutoff"]
        MODELS["Lead / worker models<br/>Intern 4B · Junior 8B · Middle 70B · Lead frontier"]
        GW --> GUARD --> MODELS
    end

    USER --> GW
    GW --> LOG[("requests.db — SQLite<br/>tokens, accounted cost, traffic_kind")]
    LOG -. budget counters .-> GUARD

    subgraph loop["Supervision loop — asynchronous"]
        LEDGER["Ledger — metrics.py<br/>deterministic analytics, no LLM"]
        ANALYST["Analyst — small local model,<br/>narrates telemetry on demand"]
        SHADOW["Shadow Evaluation —<br/>offline replay on cheaper tiers"]
        JUDGE["Judge — supervised LLM worker<br/>calibration set, temperature 0,<br/>own accounting alias"]
        CHIEF["Chief-judge review (Lead / human),<br/>mandatory for table status changes"]
        LEDGER --> ANALYST
        SHADOW --> JUDGE --> CHIEF
    end

    LOG --> LEDGER
    LOG --> SHADOW
    SHADOW --> TABLE["DELEGATION_TABLE.md —<br/>4-state evidence log (D-0035)"]
    CHIEF --> TABLE
    TABLE -.-> ROUTER["Router — DEFERRED (D-0029):<br/>built only if the R-gate opens;<br/>first task = evaluate RouteLLM"]
    ROUTER -.->|"would route scoped tasks"| GW
    ARCHITECT([Architect — human]) -->|"policies, gate signatures"| TABLE
```

This is the target scheme, drawn honestly: everything with solid
edges is operational today; the Router is drawn dashed because it is
deliberately deferred (D-0029) — it earns its place in the diagram
because the rest of the system exists largely to decide, with
receipts, whether it should ever be built. The judge and chief-judge
loop (§6) is part of the core scheme, not an appendix: it is the
component that turns replay output into evidence. Since 2026-07-07
the same discipline also runs on a second, subscription contour
(Claude Code with tiered subagents, D-0034): §4.1 explains why that
contour is a portability claim, and §5.1 why its evidence stream is
different by design.

The full specification is ARCHITECTURE.md; the reference
implementation is `gateway/`. Design choices that matter for the
argument:

- **One interception point.** All model traffic passes through a
  single proxy. This is what makes enforcement, accounting and replay
  possible at all.
- **The model hierarchy is a delegation ladder**, not an org chart:
  Intern (4B local) → Junior (8B) → Middle (70B-class) → Senior/Lead
  (frontier API) → Architect (human). Work flows down when evidence
  says it can; escalation flows up on failure.
- **Off-the-shelf over custom** (D-0030): the gateway is LiteLLM, the
  log is SQLite, the metrics are pure Python. Custom code exists only
  where it is the contribution: the supervision economics.
- **The Router is deferred** (D-0029). Routing is commoditized
  (RouteLLM); building one before telemetry shows what is worth
  routing would be architecture for its own sake.

## 4.1 The Second Contour: the Policy Is the Router

The operator's real Lead is a Claude Code subscription session, and
it cannot be routed through a proxy (D-0034). On that contour nothing
in the running system is a routing component: routing decisions are
made by the Lead session itself, reading an auto-loaded policy file
(the project's CLAUDE.md); the harness supplies only the dispatch
mechanism — subagents with a model bound per tier (recon on a small
model, implementation-to-spec on a mid model, review on a strong
model). Porting the system to a different model family or harness
therefore means porting a POLICY, not software.

What is substrate-independent by design (D-0005): tiers defined by
FUNCTION (recon / implementation-to-spec / review /
decomposition-and-acceptance), not by vendor models; delegation down
by default with escalation after two rejected attempts; flat
delegation — workers never spawn workers (D-0037); a definition of
done in every dispatch (D-0054); acceptance by trail and witness
(D-0046, D-0052); the journal event vocabulary (D-0053); and the
four-state evidence table with its weekly calibration loop (D-0035,
D-0047). A new deployment must supply exactly four things: a
tier→model binding; a dispatch mechanism the coordinator can
physically call; the policy AUTO-LOADED into the coordinator's
context — delegation is opt-in and silently dies without this
(D-0041; the finding that established it, F-1, is itself journal
evidence); and a telemetry source for calibration (transcripts or a
request log).

Evidence does NOT port with the policy. Table statuses bind a task
type to a CONCRETE model, not to a tier label: "classification →
intern is rejected" is a fact about one 4B model, not about small
models. A new model set starts at `estimated` (D-0028, D-0035) and
earns its statuses through its own acceptance stream or Shadow
Evaluation — the policy tells a new deployment HOW to decide and how
to accumulate evidence, not where its tier boundaries lie. The API
contour already runs non-Claude models under this exact discipline
(a 4B local intern, a 70B middle, a Gemini lead alias): the
discipline was never vendor-specific.

The portability claim rests on keeping two vocabularies apart
(D-0062). **Functions** — scout / builder / critic / Lead (recon /
implementation-to-spec / review / coordination) — are the only
vocabulary the policy rules speak; they are substrate-free.
**Grades** — intern / junior / middle / senior — are price/capability
steps of MODELS, used by accounting and the delegation table. A
deployment is exactly a binding of functions to concrete models; a
grade appearing inside a routing rule is a vocabulary defect. The
bridge table lives in ARCHITECTURE.md ("Two Vocabularies"). This is
what lets the same policy text run Claude subagents on one contour
and a 4B-local/70B/Gemini ladder on the other without rewriting a
single rule.

Since 2026-07-12 the portability claim is demonstrated rather than
argued: the policy was packaged as a public installable template
(Supervised-Delegation v0.1.0, D-0070) and validated by two
independent installs — a stranger's session on a fresh empty project
and the operator's self-install into an existing, unrelated project.
Both reached the first delegated cycle. Onboarding EXAMINES the
user's models before binding them to functions — a generated scout
exam and a seeded-defect critic exam dispatched as an ordinary
unmarked review (D-0071) — which is the "evidence does not port"
rule made executable: a new deployment's models earn their bindings,
they do not inherit ours. The dogfooding deployments and the
published template are kept as an explicit synchronized pair:
experiments live in the dogfooding repos, and the template changes
only in verified batches opened by the operator's word (D-0074).

## 4.2 Policy as Code: the Gates on the Execution Path

A policy that lives only as loaded text has exactly the reliability
of the model's attention on a given turn — the project's own journal
proves this repeatedly (F-9: the freshly strengthened rule was
silently skipped within hours). So the policy grew a code skeleton,
under one strict division of labor (D-0063): **code guarantees the
ENCOUNTER with a rule and decides only the deterministically
decidable; the verdict on meaning stays with a tier above the
performer.** Promotion from text to gate is evidence-driven — a norm
becomes code when the journal records it leaking, not for symmetry.

The gates, in the order a working session meets them: at session
start a WIRING check verifies the enforcement chain itself is alive
(git hooks path set, every configured hook file present and
importable — a dead hook is otherwise indistinguishable from "all
passed"). During work, dispatch-time hooks snapshot reviewer
context and record every verification run deterministically; the
journal write-moment hook validates each new event's shape, echoes
tier declarations, cross-checks builder witnesses against the
recorded run track, and compares event timestamps against the
system clock (a narrated timestamp is caught as it lands, not at
the weekly audit). A stop-gate refuses to end a coordinator's turn
whose edits lack a green verification run; a hygiene hook warns on
command forms that break allowlists or bypass the write tools. At
commit time, a pre-commit validator enforces the journal's
append-only prefix, typed fields and acceptance matrix; the
escape-allowlist checker verifies every standing policy concession
still hash-matches the decision that authorizes it; and a
commit-msg gate rejects a mechanism commit that lacks the
four-questions axis block and a tier declaration.

Three properties keep this honest. **Warn and block are chosen per
channel** — write-moment checks warn (batch and retroactive writes
are legitimate; the coordinator judges), commit-path checks block
(nothing legitimate needs a malformed journal line in history).
**The chain protects itself**: a self-activating enforcement file
is never placed on the execution path by the worker who built it —
the coordinator places it at acceptance (D-0069) — and editing a
gate is itself gated. And **the journal the gates defend is typed
for machines** (D-0053, D-0076): events record accomplished facts,
never intentions — a dispatch line exists only after the dispatch
call returns and carries the worker's handle — batched to stage
boundaries (D-0079) so discipline does not tax every turn, with
questions routing strictly up (D-0077): no tier, including the
coordinator, absorbs a decision that belongs to the user.

## 4.3 Onboarding: Mapping, Not Copying

If the policy is the router (§4.1), then shipping the system to a
new project means shipping a policy — and the naive way to do that
is to copy the reference deployment wholesale: policy file, agent
roles, journal, gates. That works exactly once — on an empty
project. A project that already runs its own agents has its own
acceptance machinery, its own carriers, its own escalation habits;
a copy either breaks them or gets rejected.

We learned this from our own pilot. When the reference deployment
shipped a batch of four mechanisms to the pilot project, the
pilot's coordinator adopted three of them — each ADAPTED to the
pilot's native carriers — and refused the fourth (judge-accepted
leaf routing, D-0087) with a precise argument: the function was
already covered by the pilot's own pipeline gates (a functional
analog of the calibrated judge), and the mechanism's prerequisites
— the gateway, the pinned judge prompt, the calibration set, the
per-task cost measurement — did not exist there, so a "judge"
acceptance basis without a calibration grid would have been a
self-certification channel, the exact defect class the mechanism
exists to prevent. That refusal was the correct move. But it took
a host that had already internalized this project's culture; a
foreign project will not reproduce it. The mapping procedure must
therefore be part of the product, not a virtue of the receiver
(findings F-51 and F-35; decision D-0090).

Onboarding under D-0090 is an examination, not an installation:

1. **Intake inventory.** The first onboarding task is an
   evaluation, never a build (D-0030 extended from models to the
   host's scheme): for each FUNCTION — acceptance, journaling and
   accounting, escalation, isolation, calibration — what covers it
   in the host today? The functions vocabulary (D-0062) is the
   bridge: the questionnaire asks "who accepts finished work here",
   never "where is your judge".
2. **The adoption ledger — a delivery norm.** For every mechanism
   in the kit the ledger records one status: adopt / native-
   equivalent (a "recognized difference": the host's own mechanism
   covers the function, and the correspondence is written down) /
   deferred (prerequisites missing; the reopening trigger is named)
   / rejected (the host's own cost-of-supervision judgment). The
   ledger is audited by the host's calibration for drift.
3. **Prerequisite closure.** Every kit mechanism carries a manifest
   of its prerequisites; installing a mechanism without them is
   forbidden by construction — either the bundle lands whole, or
   the native form stays and the ledger says so.
4. **Measure first, warn first.** The first installed layer is
   accounting only, as an adapter OVER the host's carriers — their
   journal stays their journal, nothing is migrated. Gates arrive
   warning-only and are promoted to blocking on the host's own
   evidence of leaks (D-0063). Improvement is demonstrated in the
   host's numbers before enforcement is proposed.

The empty project is not a separate path but the degenerate case of
the same procedure: the intake inventory returns an empty map, every
ledger status is "adopt", and the full default kit lands — with the
enforcement ladder collapsed (there is nothing to break) and the
accounting baseline accruing from the project's first day. The mode
is decided by the inventory map, never by declaration, so mixed
cases (no agents, but living CI and tests) resolve line by line.
Validation of the procedure is registered on two polygons — one
greenfield project and one living foreign project — with the intake
inventory as the first task of each.

Delivery does not end at install. The first upgrade of a live
deployment exposed the second half of the problem (F-52): a batch
refreshed the policy kernel but never revisited the role files, so a
critic role installed before a key rule was born kept its blind spot
for ten days — caught only by the deployment's own entrance exam,
after the fact. The ledger, it turned out, answers "what did we
decide?" but not "against which kit?": rows carried no revision, so
an outdated, incomplete mirror of the current template looked
complete. The upgrade layer (D-0091) closes this: every ledger
records the kit snapshot revision it was last reconciled against; an
upgrade re-inventories by the REVISION DELTA — role-file CONTENT
included, not just model bindings — and every delta item gets a
ledger decision (at least deferred; silence is not a decision), with
ledger completeness checked against the current template's row
nomenclature and adopted role edits passing the host's own exam gate
before commit. An adopt row is also a wiring commitment (D-0092):
the host's wiring check reads the ledger's adopt rows and warns when
an adopted mechanism's hook has silently fallen off the execution
path. Detectors sit on both ends of the channel: a staff-side
calibration check on every outgoing port batch (the kit delta vs the
target's recorded revision) and a host-side ledger
drift-and-completeness check.

## 5. Evidence-Based Delegation

DELEGATION_TABLE.md is the system's decision surface: task type →
cost of Lead → value of Lead → delegation target → status. Statuses
form a four-state model (D-0035): every row starts as `estimated`
(an expert prior, not a measurement) and may move only with evidence
attached (Update Rule 1) — to `provisionally_validated` (confirmed
on synthetic or small samples; deliberately renamed from "validated"
so the label cannot read stronger than the data), to
`production_validated` (real traffic, sufficient volume, task-level
cost — the only status that may justify routing real traffic), or to
`rejected` (delegation attempted and found harmful). On the
subscription contour status moves happen only at the weekly
calibration (D-0047), never mid-stream. The first such calibration
ran 2026-07-11 (18 checks at the time — the checklist has since
grown to 33 as new mechanisms registered their detectors; a
journaled `calibrated` event) and moved
the four Claude-contour rows — recon, implementation-to-spec,
review, coordination — to provisionally_validated on 3.4 days of
routed production traffic: the first status movements backed by a
production journal rather than replay.

Evidence comes from **Shadow Evaluation** (`gateway/shadow_eval.py`):
a sample of real Lead requests is replayed offline on a cheaper
model, and an LLM judge — never the difflib heuristic alone — rules
whether the cheap answer accomplishes the task as well as the
original. Guards built from early mistakes: a model is never compared
to itself; judge traffic is excluded from sampling; a run aimed at
one table row cannot update rows whose delegation tier differs from
the replay target (`--categories`); comparison must eventually use
total task cost including retry loops, not per-request cost.

The methodology's first real results (n=2 per category, free-tier
models; see §7) already overturned two intuitions: character
similarity is unusable as a verdict (it rejects verbose-but-correct
answers), and "classification is easy for small models" is false in
the one case where reasoning quality mattered. A later paid-source
replay cycle (2026-07-11..13; a paid Sonnet-tier source, ground-truth
task categories travelling in request metadata to a stored column,
so heuristics no longer decide what a replay was about) delivered
the sharpest reversal yet: "routine code generation delegates to
Middle" — provisionally validated on a free-tier source — collected
four consecutive reject runs against the paid source (31 judged
pairs, pass rates 0.00–0.05, chief-judge audits upheld), and the
accounting showed that on micro-tasks the paid frontier source was
CHEAPER end-to-end than the delegation it was supposed to justify:
short frontier answers cost less than a verbose local intern at
synthetic accounting prices. The earlier verdicts were facts about a
FREE source's economics; the row's fate is the next calibration's
call (§7).

## 5.1 Contour Asymmetry and the Regression Bridge

Shadow Evaluation exists only on the API contour, and that is a
design decision, not a gap. Replay needs an interception point and a
prompt→text task shape; the subscription contour has neither — the
subscription Lead cannot be proxied, and interactive agentic work
(tools, repository state, multi-turn sessions) does not reduce to a
replayable prompt.

The subscription contour therefore validates delegation in
PRODUCTION instead of counterfactually: work is dispatched down by
default, and the journal measures whether the tier coped —
rejections carrying a failure class, escalations, late defects of
already-accepted work (`defect_found`), and acceptance that must
present evidence (a search trail for recon, an actual test-run
witness for implementation). The weekly calibration aggregates this
stream into table-status movements. The one question replay answers
and this stream cannot — could the work the Lead kept for itself
have gone down? — is compensated structurally: every self-exemption
is a visible journaled event (`dispatch_skipped`, reason mandatory)
audited by calibration, and the policy default is down.

As of 2026-07-08 this is no longer a design sketch: the routing MVP
runs on two deployments (a pilot project and this repository itself
— the reference, dogfooding deployment), and the policy text was
Architect-accepted on 2026-07-09. The evidence stream is typed, not
prose (D-0053): load-bearing facts are journal FIELDS — `attempt`
and a `failure_class` word (spec / capability / recon / tooling) on
every rejection, the verbatim run output as `witness` on every
builder acceptance, a `ref` on `defect_found` that retro-attributes
a late defect of accepted work to its original dispatch. Every
dispatch carries a tier-shaped definition of done (D-0054): a worker
returns a DoD-less dispatch with questions instead of starting.
Acceptance authority follows the ACTUAL model of the accepting
session, not the policy's addressee (role ≠ tier, D-0058):
acceptance is legal only from a tier strictly above the worker, a
critic verdict is the recorded exception, and an equal-tier
coordinator queues acceptance to the full Lead — otherwise a session
would certify itself. Parallel dispatches and sessions declare owned
paths and never touch another session's uncommitted work; task-id
novelty is checked against the journal tail at write time (D-0060).
Since D-0073 every dispatch also carries a context MANIFEST next to
its definition of done: the injected "given" basket, plus
owns/non-goals/handoff on writing dispatches — declarative on reads
(reading past the basket is a report line, not a violation),
normative on writes. The journal format and the acceptance matrix
are enforced by a pre-commit validator on the commit path (D-0069),
and every mechanism commit must declare its tier in the message,
checked against the deployment's lead binding (D-0072). The first
weekly calibration ran 2026-07-11; the loop is now a standing
weekly operation and the only place table statuses move.

The two streams are bridged, not merged. Accepted journal tasks that
distill to a replayable form (recon questions, spec→diff,
summarization, extraction) become a regression set run on the API
contour when tier models or prices change. The set is biased toward
text-shaped tasks and its evidence is labeled per category, never as
"the whole tier". Replayed traffic is tagged `traffic_kind='replay'`
and never counts toward phase gates — the gates feed on REAL traffic
only (D-0033), and that real-traffic diet is supplied by the
subscription contour. This is also why the API contour needs no
working project of its own to do its lab job: it validates quality
and prices; the money-on-the-table questions are measured where the
real work happens.

## 6. The Judge Is a Supervised Worker

The judge is the architecture's recursive step, and empirically its
most fragile component. Three findings from calibration
(gateway/judge_calibration.json, 13 human-labeled pairs):

1. **Judges fail by capability, not by prompt.** A 70B judge
   consistently ruled a correct fibonacci implementation WORSE. Two
   prompt fixes aimed at the assumed cause (strictness) changed
   nothing; a diagnostic "explain your verdict" showed the model
   hallucinating a bug while tracing correct code. The fix was a
   stronger judge (120B reasoning model, 13/13), not a better prompt.
2. **Judging capability tracks the same hierarchy as working
   capability.** On the identical pair set: 4B misses both hard pairs
   (code tracing + borderline sentiment), 70B misses code tracing,
   120B passes all 13. Judging code is Senior-tier work — catching
   someone else's bug requires solving the task yourself *and* not
   trusting your own hallucination.
3. **Verdicts are stochastic unless pinned.** At default temperature
   a borderline pair flipped between consecutive calibration runs;
   judge calls now default to temperature 0.

Consequently the judge is supervised like any other worker
(PROCESS/JUDGE_CALIBRATION_PROTOCOL.md, D-0031): verdicts that change
a table status require chief-judge (Lead or human) review of the
actual pairs; every reviewed pair grows the calibration set; 1–2
random verdicts are audited per run; recalibration happens every ~5
new pairs; and the judge model is upgraded only on measured agreement
degradation below 90% — never preemptively.

Two later findings extend the theme upward. First, cross-family
judging is bound by the same calibration bar: a second judge from a
different model family (a Gemini flash tier, 13/13 on the same set,
but 20 requests/day) is bound for point work only — cases where the
primary judge would be grading its own family's output. Second, and
more general: **evaluation instruments saturate from below** (F-28).
A rubric exam built to qualify Lead-tier candidates was passed by a
builder-tier control with the day's best score — so a passed exam is
an ENTRANCE FILTER, never a tier discriminator, and any instrument's
verdicts are usable only after control runs by candidates of KNOWN
tiers (the judge-supervision principle applied to exams themselves).
A purpose-built ranking exam (six cases distilled from production
incidents, rubric and threshold pre-registered before the first run)
confirmed the ceiling honestly across three runs: the only frontier
delta measurable by vignettes at all is the INDEPENDENT-reproduction
reflex — verifying a suspect claim yourself or via another source
rather than requesting more evidence from the same fallible source.
On that diagnostic pair: Opus 2/2, a Gemini 2.5-flash cross-family
candidate 1/2, the Sonnet control 0/2. Everything else saturates.
The top of the hierarchy is ranked by production telemetry (cost per
accepted unit, escalation rate, late defects), not by exams.

## 6.1 Accounting Prices, Not Cash Prices

Free tiers and local models would make Rule #1 unverifiable if cost
were recorded as cash spent. The system therefore accounts every
alias at a nonzero price — the provider's paid-tier price for
free-tier APIs, synthetic Haiku-class prices for local models — and
treats a free tier as a cash discount, not a cost of zero (D-0032).
Supervision cost (Analyst, judge) is logged under dedicated aliases
so it can never hide inside work-model spend.

## 6.2 The Coordinator Is a Supervised Worker Too

The sharpest finding of the first dogfooding week is about the Lead
itself. Worker claims were already evidence-gated (trail, witness);
the coordinator's own claims were not — and the journal recorded a
characteristic defect class (F-30): **treating one's own unverified
inference as verified fact.** Documented instances within one week:
timestamps written from the session's narrative instead of the clock
(F-29); a quota wall that counted only its own ledger while the
provider counted everything, aborting an exam three times (F-27); a
"the window has reset at midnight" assumption where the window was
rolling; cwd persistence assumed rather than checked. The decisive
observation: the live Lead committed all four case-bank errors in
production ON THE SAME DAY candidate models solved the same
situations flawlessly as text vignettes (§6). The defect lives in
behavior-in-flow — long context, goal inertia, missing data — not in
knowledge, which is why exams cannot reach it and why the defense
must stand on the execution path.

The defense follows a general principle the project adopted as
**two-layer enforcement (D-0063): code guarantees the ENCOUNTER with
a rule and decides only the deterministically decidable; an AI tier
above the performer judges fulfillment in meaning — never inferred
from syntactic proxies.** Concretely, for the coordinator: hygiene
rule — any load-bearing claim about the environment (quota, time
window, resource availability, "already running") is valid only
with a measurement attached, or must carry an explicit "estimate,
unverified" tag; quota-bounded runs can only launch through a
preflight gate that measures all local ledgers plus the provider
and refuses on shortfall — launching on an unmeasured assumption
becomes impossible by construction; a session-start hook prints
ambient reality (actual clock, journal tail, open degradation
window, calibration age, quota windows) so the facts the model is
tempted to narrate are already printed; and a pre-commit validator
enforces the journal's typed fields, task-id novelty and timestamp
sanity — each check a direct code trap for a defect that actually
occurred. Discipline-held rules are promoted to code gates on
journal evidence of leaks, never for symmetry (Rule #1 applied to
enforcement itself).

The same skepticism covers the coordinator's identity and authority.
A session's tier is what its ACTUAL model is, verified at both entry
and exit (D-0056); an operator switch to a cheaper model — or a
provider-side refusal — opens an explicit, journaled degradation
window with reduced authority (no mechanism, status or decision
changes while degraded), and restoration includes acceptance of the
window's work (D-0039..D-0044). And every mechanism the project
adds must answer four questions in writing before it lands (rule
10): (a) what compliance costs and who pays — Rule #1 applied to
the rule itself; (b) which symmetry axes of the deployment map it
covers, answered by per-axis enumeration, not prose; (c) where its
failure DETECTOR is registered — a mechanism without a registered
detector is a wish, not a mechanism (D-0049); (d) what stands on
the execution path to keep it from being skipped (D-0064) — "held
by discipline" is legal only as an explicit line naming the
detector. A commit-message hook enforces (b) deterministically;
the recognition of "this is a mechanism" is itself defended in
depth (D-0065), with a stated admission that 100%-by-code is not
promised.

The same week extended the principle one layer down: the
MEASUREMENT is a supervised component too. Two accounting defects
were found and closed by construction rather than by vigilance
(D-0075, F-37/F-38). Every non-organic traffic generator now
self-tags its rows — organic clients cannot tag, so 'real' stays
the default and everything synthetic must say so in its own
payload. And a cache-share formula that double-counted was traced
to field SEMANTICS assumed from a sibling instead of verified: the
same metric's input field INCLUDES the cache components on one
contour and excludes them on the other. The recorded rule: porting
a formula across a measurement pair translates field semantics,
never copies arithmetic — and semantics are verified empirically on
live rows, not by reading the sibling's code.

## 6.3 The Deployment Exam: A/B-Testing the Policy Itself

If the judge and the coordinator are supervised workers, the last
unexamined component is the deployment as a whole. The savings
report is observational — actual spend against counterfactual
prices, with no control group — so it cannot answer the question
that matters: **does the delegation policy help, hurt, or merely
cost?** The deployment exam answers it by controlled comparison.
The same model, the same harness and the same tasks run in up to
three arms: **A** — the bare model in an empty project; **B** — a
fresh install of our full deployment (policy, tiered agents,
journal, gates — the template's boot tax honestly included, since
"boot context is paid" is our own thesis); **C** — a strong user's
cheap alternative: no infrastructure, just a one-line prompt asking
the model to use subagent workflows. C is the arm that keeps B
honest: if C ≈ B, we are hauling dead weight.

Tasks are deliberately UNDERSPECIFIED, the way real requests are
("write me a calculator"). A fully specified task is worker-class
work — any competent model passes it — and would exercise nothing
of the coordination layer the exam exists to measure: turning
intent into a plan, choosing an architecture, deciding what to
delegate and to whom, asking the user when the intent forks.
Acceptance keys are pinned before the run at the level of INTENT
(what the result must be able to do), never as an implementation
spec; a key that silently encodes one interpretation of an
ambiguous intent is itself a defect of the exam — a lesson learned
when the operator overturned such a verdict. Arms never see the
keys, and the run is not announced as an exam: working behavior is
what is measured. Headless runs get a recorded prosthesis for the
question channel — a proxy verdict from the deployment's top-tier
model stands in for the unavailable user, marked as such.

**Quality is a vector, not a pass/fail bit.** Early runs used
binary acceptance plus a small rubric and found them blind exactly
where it mattered: an arm can pass every checklist item while its
cheapness is paid for by invisible quality debt. The current
scorecard has five axes in [0,1]: adversarial correctness
(pre-pinned probe battery, identical for all arms), completeness
against intent, TEST QUALITY measured by mutation kill rate — seeded
defects of pinned classes must make the arm's own tests fail (test
COUNT proved meaningless: an arm with 37 tests killed fewer mutants
than a sibling with 22), persistence of evidence (acceptance
reproducible from files alone), and auditability. A weighted sum
gives the scalar; **F = dollars per weighted quality point** is the
single Rule-#1 number that lets a cheap-but-hollow arm and an
expensive-but-solid arm be compared honestly. The vector did in
practice what the rubric could not: it shrank a phantom 45% cost
advantage of the no-infrastructure arm to ~10% by pricing in its
zero tests and non-reproducible acceptance.

The exam comes in two sizes. The SMALL exam — three ~10-minute
tasks (a product from scratch, a survey of a foreign repository, a
bug fix in existing code) — is cheap enough to run at every weekly
calibration; since single runs are noisy (a factor-of-2.6 spread
between identical configurations was observed), no single run
decides anything: verdicts accrue to the MEDIAN across calibration
runs. The LARGE exam — one multi-session project driven through
sequential fresh sessions — runs at release cadence only. Runs are
driven by an automated runner from a pinned manifest; sandbox
composition is diffed against its declared sources (an assembly
error that silently mixed two configurations was caught only by its
effect and is now checked by construction); the measurement window
itself is measured, not declared, after two "clean windows" proved
to carry parallel load.

What the exam series has decided so far — each verdict a recorded
change to the deployment, none of them decided by intuition:

- **The critic diet is closed.** A monotonic five-point trend
  showed that every step of restricting the reviewer (by text, by a
  call limit, by the full restricted bundle) made results both
  worse and more expensive; the per-diff critic returned as
  standard. What survived from the diet is its coordinator-style
  savings: batched journaling and bulk acceptance.
- **Text does not program a mid-tier coordinator; code does.** A
  policy-text instruction to change review cadence was read and
  ignored by the field session; the same rule as a hook held
  perfectly (zero false blocks across the gate series). This
  confirmed two-layer enforcement (§6.2) on the coordinator itself
  and produced the policy-as-code gate set now active in the
  deployment: dispatch hygiene, edit-without-green-run blocking for
  workers AND for the coordinator's own main thread — the latter
  because forensics showed the main session was the one surface no
  subagent-scoped gate could see.
- **Questions routed upward pay for themselves.** In the large
  exam, the only arm that asked the user-proxy before choosing an
  interpretation won on quality — the operator's verdicts went "who
  asked, won" — turning the question-routing rule from etiquette
  into a measured economic asset.
- **The bare-prompt alternative is cheaper and structurally
  hollow.** Arm C reliably underprices B on small tasks and
  reliably ships without persistent defenses: zero tests on the
  from-scratch task, surviving mutants on the bug-fix task, its
  review quality a lucky property of one conversation rather than
  an invariant of the process. On survey-class work its
  impromptu fan-out was both slower and costlier than B's policy.
  The honest current reading: on ~10-minute tasks the
  infrastructure roughly breaks even on F and wins on quality
  durability; its designed advantage is the regime where quality
  debt compounds — which is exactly what the accruing median
  exists to test.

## 6.4 Driving the Price Down: What We Tried, What Held

Once the exam could price quality honestly, it became the
instrument for a deliberate cost-reduction campaign. The campaign
is worth recounting in full — including the direction that failed —
because the pattern that emerged is more useful than any single
number.

**Diagnosis first.** The early runs and the coordinator forensics
agreed on where the money actually went: not into any single
expensive answer, but into COORDINATION OVERHEAD — per-event journal
writes, piecemeal acceptance of workers, clarification loops (the
micro-cycle tax), and the reviewer's reading habits (on one
calculator-sized task the review tier spent 101 turns where the
implementation needed 105). Dispersion between identical runs was
×2.6, so every candidate cut was given a pre-registered bar and
measured against the accruing median, never against a single point.

**The direction that failed: starving the reviewer.** The intuitive
cut — the reviewer is the most expensive tier, so restrict it — was
tried three escalating ways (§6.3): softer review by text, a
hard call limit by hook, the full restricted bundle. The five-point
trend was monotonic and damning: quality fell from 0.93 to 0.65
while cost per accepted task ROSE. Removing judgment does not make
a system cheaper; it makes rework and defect debt, and the exam
priced that debt visibly. The diet was closed as a recorded verdict.

**What held, cut one: move the mechanics down-tier, keep the
verdict up-tier.** The successful reviewer economy was a
reassignment, not a restriction. In the two-layer scheme the
MECHANICAL layer — re-running tests, control values, smoke matrices
— is executed by the submitting worker or a script and attached
verbatim BEFORE the verdict; the top-tier reviewer's zone narrows to
what actually requires its intelligence: architecture, semantics,
class completeness of a fix. On the same task set this held the
scalar (0.95, the series' best band) at −37% price; review-tier
turns on the calculator task dropped 101 → 27, and a boundary-test
defect class that had survived four runs died the first time the
narrowed reviewer was pointed at it. Forensics added a nuance worth
recording: the savings came from FOCUSING the verdict (less reading,
fewer loops), not from skipping re-runs — the reviewer still
re-ran the cheap checks, which is fine, because re-running attached
evidence costs pennies while re-deriving it costs the expensive
tier's attention.

**What held, cut two: batch the coordinator.** The micro-cycle tax
was attacked directly: journal events accumulate and land as one
batched append at stage boundaries; small non-blocking edits are
never self-executed piecemeal by the coordinator but accumulate
into a single batched dispatch; worker acceptance happens in bulk
at stage boundaries. The measured effect on the coordinator's
self-execution stream: sixteen piecemeal skip-class actions in the
baseline window, one in the window after the rule — with the
batching economics confirmed rather than assumed at the next
calibration.

**What held, cut three: put the always-loaded context on a diet and
make the exam prove it kept its teeth.** The auto-loaded policy is
a per-session tax on every session of every day. It was rewritten
as a norms-only kernel — rationale, precedents and history moved to
an on-demand companion — cutting the boot payload by 41%. The risk
(a policy that loses its teeth when its explanations leave the
context) was treated as an empirical question: three exam runs with
pre-registered keys, compared against the full-policy band. The
kernel held the band (0.94 / 0.90 / 0.92 against a 0.93–0.95
recent full-policy band) — and when one run showed journal
discipline slipping (eleven malformed journal lines), the fix was
chosen the same way the reviewer fix was: not more prose, but a
shape TABLE in the kernel plus a write-moment validation hook that
warns the author the instant a defective line lands. The next run's
journals were defect-free, and the hook caught its first real
mistake in the authors' own deployment within an hour of being
installed.

**The net effect,** measured on the same three-task set, same
coordinator model, with the caveat that these are few-point series
under ×2.6 dispersion: cost per accepted task on the full-policy
arm fell from $6.01 (scalar 0.94) to $3.81 (0.95) with the
two-layer review, to $3.38–4.16 (0.90–0.96) on the dieted kernel —
roughly a 40% reduction in dollars per weighted quality point
against the section's opening baseline, with the quality vector
held rather than traded away.

The pattern, stated once: **every cut that survived removed
overhead or relocated mechanical work to a cheaper executor; every
cut that failed removed judgment.** And every one of these
decisions — including the failed diet — exists as a pre-registered,
measured, recorded verdict that the next calibration can re-check,
which is the difference between a cost-reduction campaign and a
cost-reduction anecdote.

## 6.5 One Path: Leaf Routing and the Judge-Accepted Leaf

The cost campaign of §6.4 ended with an uncomfortable diagnosis:
after the policy had already taken the easy routing prize, the
remaining money was not IN the routed work at all. The original
Router-gate criterion ("validated delegable categories account for
≥25% of spend") measured 0.01% — a prize the static policy had
already collected. Re-measured by the main-vs-sidechain method, the
coordinator's own loop — allocate, dispatch, accept, journal —
accounted for roughly 85% of the construction's spend. The gate was
re-registered around the honest prize (D-0086): the question is not
"which category to route" but "can the coordinator leave the loop
without quality following it out".

**The pre-registered experiment.** The D-construction: intake
classifies a task as a LEAF (one performer, one allocate-category,
no dependencies; any doubt makes it a graph) or a GRAPH; a leaf runs
an automatic path — static category ladder picks the tier, the
worker executes, and a CALIBRATED JUDGE accepts or rejects against
the dispatch's acceptance keys, with a deterministic escalation
mirror (one retry on the same tier, one one-step escalation, then
failed back to the coordinator). The Lead never enters the leaf
loop. Keys were pre-registered before any run: cost per accepted
task ≤ the classic arm, quality within 0.05 of the Lead-accepted
band, wall-clock no worse. Six series runs delivered the keys —
median $2.08 per accepted task against the $2.60 bar, quality
median 0.975 against a 0.87 floor, wall-clock 17.1 minutes against
18 with parallel launch — and the gate was signed open on that
evidence (2026-07-21), the first task of the workstream having
already been delivered by the same series.

**What did NOT win: a learned router.** Six router candidates from
the literature and the ecosystem were evaluated across two survey
waves against our own labeled ground truth; all six were rejected
(the strongest, a BERT-class classifier, scored AUC 0.60 on the
exam slice — a coin with a limp). The adopted construction routes
by a STATIC category ladder plus a judge at acceptance; the learned
router stays rejected until a pre-registered reopen trigger
(≥100 labeled examples) fires. This is worth stating plainly
because it inverts the field's default: the interesting decision
automation was never "which model answers" — it was "who accepts
the answer".

**The judge exists on both supply channels.** The gateway judge is
calibrated 13/13 (§6); the subscription channel gained an
equivalent form — a subagent carrying the pinned judge system
prompt VERBATIM scored 13/13 on the same calibration set the same
day (t-254). A drifted judge prompt is a finding, not a judge. With
both forms live, the leaf path is a property of the POLICY, not of
any particular API contract.

**The architectural consequence (D-0087/D-0088).** Leaf routing
became kernel rule R13, and the two "contours" that had organized
the project since D-0034 were demoted to what they empirically are:
model SUPPLY-AND-MEASUREMENT channels. The task path is single and
forks by SIZE at intake — leaf or graph — not by billing contour.
Execution, acceptance discipline, the escalation ladder and the
journal are contour-independent; what stays channel-specific is
replay (API only), judge calibration (gateway), and two-source
accounting. The journal carries the new acceptance basis as a typed
field (`basis: "judge"`), the validator enforces it, and a
calibration check audits every judge-accepted event for class
violations — a mechanism/policy/integration change accepted under a
judge basis is self-certification and is flagged by construction.

## 6.6 Making Acceptance Machine-Checkable: the Validation Layer

Two-layer enforcement (D-0063) says code guarantees the ENCOUNTER
with a rule while a higher tier judges MEANING. Through mid-July the
meaning layer was well-guarded and the encounter layer was thinner
than it looked: a witness was a non-empty string, a reviewer verdict
was free text, a hook could die silently, and a standing policy
concession could outlive the decision that justified it with nobody
noticing. A two-pass survey (D-0066) of an outside evidence-first
harness supplied the missing patterns; four mechanisms were imported
in one wave, each passing the four-questions discipline and a
critic gate before landing:

1. **Wiring integrity.** The session-start hook now verifies that
the git hooks path is set, that every configured harness hook file
exists and imports, and that the interpreter is reachable — loudly,
as data lines in the boot report. A silently dead hook is otherwise
indistinguishable from "all checks passed" (the same class as the
silent-$0 accounting failure).

2. **Witness cross-check (evidence-v2).** The journal write-moment
hook cross-checks every builder acceptance's witness against the
deterministic run track that a post-tool hook already records:
the witnessed command must have actually run in-session, and a
witness whose command ran red is a contradiction worth a warning.
Absence alone never blocks — batch, cross-session and retroactive
acceptance are legitimate — but a narrated witness that contradicts
the observed track is caught at the moment it is written, not at
the weekly audit.

3. **Schema verdicts from a write-free reviewer.** The reviewer's
final message must now END with a fenced JSON verdict — verdict
class, blockers, class-completeness answer, and a trail of files
read and reruns performed — validated by a fail-closed checker
BEFORE acceptance; the reviewer's toolset itself is read-only by
definition file. The role edit was exam-gated (§6.3 discipline): a
freshly generated seeded-defect exam, keys pre-registered, two
unmarked runs — with one trap ANNULLED as a key defect when two
independent strong runs failed it identically for a structural
reason, a ruling recorded openly and queued for the next
calibration's audit rather than absorbed silently. The mechanism
paid for itself on day one: the checker's first live use rejected a
real verdict (trail reruns submitted as strings instead of typed
objects), the resubmission passed, and the acceptance proceeded on
a machine-valid verdict.

4. **The escape-allowlist: concessions pinned to their reasons.**
Every standing concession in the policy — the small-diff review
skip, the batching exception, the judge acceptance basis, the
retro-pair rule — is now a machine-readable entry binding a text
anchor in the policy to the SHA-256 of the decision section that
authorizes it, checked fail-closed on every commit. A rule whose
justification drifts — or quietly disappears — breaks the commit
loudly. The mechanism validated itself in the strongest way
available: on its own seed data it exposed that the kernel had been
citing "D-0056b" as the authority for the journal retro-pair norm —
a sub-label that had never existed as a decision section. The
missing decision was minted (D-0089) the same night, and the seed
re-pinned. A validation mechanism that catches a hole in its own
constitution within hours of being built is the class of evidence
no synthetic benchmark provides.

The same wave codified an adjacent class found by the pilot
deployment's forensics: **deliverable drift** — work accepted
against a REAL witness whose diff is then washed out of the working
tree by a broad checkout before it is ever committed. Witness
discipline proves the work ran; nothing proved the work SURVIVED.
Acceptance and persistence are different events with a window
between them, and the window now has two checks: the evening
session-handoff verifies each accepted witness's load-bearing
entity exists in committed HEAD, and a weekly calibration check
sweeps the same property across the window's acceptances. The
forensic technique that proved the class (runtime caches — test-id
caches, bytecode timestamps — as witnesses that survive a git
checkout) is recorded as method, since git cannot rewind what git
never owned.

## 7. Empirical Status (2026-07-13; updated 2026-07-22)

What the evidence currently supports — with honest caveats: Shadow
Evaluation volume is honest only for coding (31 judged pairs across
6 runs, with a recorded caveat that pair-instances repeat prompts
across runs); other categories are still n≈2 on a free-tier source.
The subscription-contour baseline is CENSORED data (the operator
rationed frontier usage). provisionally_validated rows rest on a
3.4-day window; the production_validated bar (full week +
cost-per-accepted-unit trend) is deliberately not claimed.

API contour (Shadow Evaluation + judge, details in
docs/SHADOW_EVALUATION_LOG.md):

| Claim | Evidence |
|---|---|
| Extraction, formatting, summarization delegate to a 4B local model | Shadow Evaluation, judge-verified, pass_rate 1.00 — FREE-tier source; first paid-source counter-datapoint recorded (see micro-task row) |
| Routine code generation does NOT delegate to Middle (70B) from a paid source | four consecutive reject runs 2026-07-11..13, 31 judged pairs, pass rates 0.00–0.05, chief-judge audits upheld; the earlier free-tier-source pass (n=2) stands as the overturned prior; status MOVED to rejected-on-current-bindings at calibration #2 (2026-07-18, Update Rule 1) |
| On micro-tasks a paid frontier source can be CHEAPER than delegation | replay accounting: short paid-Sonnet answers cost less end-to-end than a verbose local intern at synthetic accounting prices — free ≠ $0 (D-0032), and delegation economics are a property of the SOURCE, not only the target |
| Paid uncached input is 0.11% of the input side; the local compression lever is dead | direct cache-aware measurement of the API window (requests.db, F-38-correct formula); provider caching works through the proxy; context-management workstream closed by Architect signature |
| Classification does NOT delegate to 4B | judge + manual review agree: flawed reasoning on a mixed-sentiment case |
| difflib similarity is not a verdict | 2 of 5 first-run verdicts were false rejections |
| 70B judge unusable for code pairs | hallucinated bug in correct code, reproduced across independent runs |
| Judge nondeterminism at default temperature | calibration flip 11/11 → 12/13 between consecutive runs |
| Judge capability tracks model hierarchy | 4B: 11/13, 70B: 12/13, 120B: 13/13 on the same pairs |
| Recon does NOT delegate to the available 4B local model | entrance + hardened re-exam 0/7 twice, fabricated citations; local-scout thread closed until a stronger model fits 6 GB VRAM |

Subscription contour (transcript telemetry + routing journal +
exams, 2026-07-07..13):

| Claim | Evidence |
|---|---|
| Cache reads dominate agentic input | 97.6% of input-side tokens are cache reads; accounted cache savings $7,117 on a $1,178 total — provider caching must be measured before any compression is built (D-0036) |
| Frontier burns fastest per turn (censored baseline; spend-share is NOT the metric) | opus $0.264/turn, fable $0.216 vs sonnet $0.063–0.114 (2–4x); success metric fixed as cost per accepted unit + escalation rate (Architect correction) |
| Rubric exams saturate one tier below the target | F-28: builder-tier control passed the Lead-qualification exam with the day's best score |
| The vignette-measurable frontier delta is independent reproduction | ranking exam, 3 runs, pre-registered rubric: Opus 2/2 > Gemini 2.5-flash 1/2 > Sonnet 0/2 on the diagnostic pair; everything else saturates |
| The coordinator is the reality-grounding weak point | F-27/F-29/F-30: narrated timestamps, one-ledger quota wall, calendar-reset assumption — all journaled within one week, defenses now on the execution path (§6.2) |
| Delegation is opt-in: policy must auto-load | F-1: with agents defined but policy not auto-loaded, the Lead did delegable work itself on the most expensive tier |
| All four contour rows provisionally validated in production | first weekly calibration 2026-07-11: scout 14 accepted / 1 tooling reject / 0 late defects (+ golden set 7/7×3); builder 11 witness-backed acceptances, 0 capability fails; critic 9 dispatches, 7 verdicts, findings confirmed by Lead spot-checks; the Lead row confirmed from the failure side — both window defects sit on the coordinator itself |
| The policy ports: two independent installs reached the first delegated cycle | toolkit v0.1.0 (D-0070): a stranger on a fresh project and the operator's self-install into an existing one; models examined at onboarding (D-0071) — the critic exam caught a real trap miss on the user's model |

Supervision cost so far: the judge's accounted spend for the entire
calibration + evaluation history remains in cents against its source
samples — trivially satisfying Rule #1 at this scale, but the ratio
only becomes meaningful with production volume. Since 2026-07-12 a
paid Lead is in production by fact, not sign-off: an "API window"
routes the operator's real interactive sessions through the gateway
on prepaid credits ($29.89 accounted on the first evening), which is
what made the cache-aware C3 measurement — and the R2/R3 gate
criteria — computable on real traffic for the first time.
Scout-tier recon economics are near zero on the subscription contour
($1.33 accounted all-time), so the standing case for cheap recon is
resilience and the API-contour pilot, not savings — recorded to
prevent overclaiming.

Accounting hardening (2026-07-04, since Architect-reviewed): Shadow
Evaluation reads proxy-accounted costs for replay targets and judge
calls (never a silent $0; historical `cost_target=$0.0000` lines are
accounting artifacts), and all traffic is tagged
real/synthetic/replay/judge — Phase 2 gates count only `real`.

Routing construction and validation layer (updates through
2026-07-22; evidence homes: DEPLOYMENT_ECONOMY_EXAM Runs log,
ROADMAP gate decisions, PROCESS/CRITIC_EXAM.md Runs log,
logs/routing-log.jsonl):

| Claim | Evidence |
|---|---|
| The honest routing prize is the coordinator loop, not category choice | R2 re-measured by the main-vs-sidechain method: validated-category spend 0.01% (prize already taken by static policy) vs coordination overhead ~85% (D-0086 re-registration) |
| A judge-accepted leaf path beats the classic loop on pre-registered keys | six D-arm series runs: median $2.08/accepted ≤ $2.60 bar, quality 0.975 ≥ 0.87 floor, wall-clock 17.1 ≤ 18 min; Router gate signed open 2026-07-21 |
| Learned routers lose to a static ladder + judge on our ground truth | six candidates rejected across two survey waves (best: BERT-class AUC 0.60 on the exam slice); reopen trigger pre-registered at ≥100 labeled examples |
| The judge is channel-independent | subscription-channel subagent judge carrying the pinned gateway prompt verbatim: 13/13 on the calibration set, same day (t-254) |
| Savings hold under routing at scale | calibration #2 (07-18): ~65% gross counterfactual savings, $3.77/accepted delegated unit; calibration #3 (07-19): 65% stable |
| Reviewer exam discipline survives role evolution | six seeded-diff exam runs across five role revisions (t-060..t-260): PASS band held; exam #2 recorded a two-run trap annulment as a key defect (openly, queued for calibration audit) rather than silently re-scoring |
| The validation layer catches real defects on day one | rule-16 checker's first live use rejected a real verdict (untyped trail), resubmission passed; escape-allowlist's own seeds exposed a dangling authority label ("D-0056b"), minted as D-0089 the same night |

External priors the local telemetry must confirm or refute (sources
in docs/RELATED_WORK.md): 50–62% of spend is re-sent history; 30–40%
of tokens are redundant; cascade routing can cut cost up to 98% at
equal quality; cheap models can need 10 retry loops where frontier
needs 1.

## 8. The Repository Is the Operating System's Memory

The second half of the "operating system" claim is not about models
but about state. This is the fix for the **inter-session** layer of
the context cost (§2): sessions become short and disposable — a new
session boots from a curated, compact context instead of dragging a
long conversation, and nothing is lost when it ends. It deliberately
does not address intra-session re-sending; that is Phase 2
compression territory. LLM sessions are ephemeral; the project treats
that as a design constraint, not an inconvenience:

- **Git is the only long-term memory.** No project knowledge may
  exist only in chat history (D-0014). Decisions carry numbered
  entries; recurring practices become protocols in PROCESS/.
- **Boot is standardized.** A new session executes BOOT.md, loads the
  constitution → decisions → operational state, and must emit a
  structured Boot Report before any work (PROCESS/BOOT_REPORT_PROTOCOL.md).
- **Recovery is tested.** Phase 0 closed only after a Zero Context
  Recovery Test: a fresh LLM session resumed the project from the
  repository alone (D-0022, D-0024).
- **Boot context is a paid resource — the project's own subject
  applied to itself** (D-0038). The boot path carries a 100 KB
  budget, re-measured at every session close; closed work moves to
  an archive the moment it closes, leaving a one-line pointer. Five
  "boot diet" rounds (D-0051, D-0067/68) split decision full-texts
  from the always-loaded index, replaced the full architecture spec
  on the boot path with a session-sized operative core, made the
  breach response itself an executable procedure (archive sweep
  first; deep cuts of operative documents only by explicit
  Lead+Architect decision) — and finally cut the policy text itself:
  rationale and gate-guarded procedural detail moved behind the code
  that enforces them (two-layer enforcement applied to the policy's
  own text), verified before commit by an independent critic review
  of the diff ("no obligation lost") and a scout golden-set run
  against the trimmed text. Current boot path: ~94 KB of the 100 KB
  budget.
- **Session close is checked symmetrically to boot** (D-0050): a
  handoff checklist verifies everything is committed and pushed,
  the journal is closed, live-state files reflect reality and the
  boot budget holds; the next session's Boot Report detects a
  skipped handoff (a dirty tree at boot is a finding, not noise).

This is self-hosting in the OS sense: the project is developed by the
architecture it describes. The Lead plans and reviews; cheaper
sessions execute specified tasks; the judge is calibrated before its
verdicts are trusted; and the human Architect holds the same role the
architecture assigns — policy, keys, and final review. Several of the
findings in §6 and §7 were produced *by* this process, including two
process failures (sampling contamination; a misdiagnosed judge bias)
that were caught precisely because review steps are mandatory.

## 9. Positioning

Existing work covers routing (RouteLLM, FrugalGPT), observability
(Langfuse, Helicone), enforcement primitives (LiteLLM budgets), and
OS-as-metaphor framings (Karpathy's LLM OS, AIOS, MemGPT). To our
knowledge no open project combines **deterministic budget enforcement
+ spend analytics + evidence-validated delegation as its core loop**,
with the supervision economics (Rule #1) as the design invariant.
Routing itself is commoditized; the contribution is knowing — with
receipts — what to route, and proving the supervisor earns its keep.

Adjacent agent harnesses (a Pi-style tool harness for gateway
workers, GSD, OpenClaw) were surveyed under an explicit two-pass
discipline — a scout maps, and a mechanism enters the plan only
after the coordinator's own targeted second pass over the promising
spots (D-0066) — and mined for MECHANISMS rather than adopted:
quota preflight, context manifests, witness auto-collection ride
our own queue as evidence allows. Adopting a coordinator-replacing
agent wholesale would forfeit the cost-crossover measurement loop
that is this project's niche (verdicts recorded in
docs/RELATED_WORK.md to stop re-litigating).

## 10. Roadmap

- **Phases 0/1/1.5 — CLOSED (2026-07-03 / 07-11):** the API-contour
  MVP (Gateway, Guard, Ledger, Analyst, Shadow Evaluation; 360 tests
  green on the canonical run), cache-aware transcript telemetry, the
  deployed routing MVP with an Architect-accepted policy, and the
  weekly calibration loop — now a standing operation, not phase
  work. Paid keys arrived 2026-07-10; since 2026-07-12 an "API
  window" routes the operator's real interactive sessions through
  the gateway on prepaid credits.
- **Phase 2 — gate decision SIGNED 2026-07-13** (gates defined by
  D-0029/D-0033/D-0036/D-0059; thresholds in ROADMAP.md; a green
  gate produces a written report and a human signature, never an
  automatic transition):
  the TASK-PIPELINE workstream OPENED 07-13 and CLOSED 07-18 by
  adoption: the harness's native task tools were REJECTED as a
  primary carrier (their store lives outside the repository, hence
  outside the project's only memory), and the piloted markdown DAG
  artifact became the standard carrier for tasks of ≥5 events or ≥2
  sessions (D-0080). The CONTEXT-MANAGEMENT workstream is CLOSED by
  direct measurement (C3 = 0.11% vs ≥25%): provider caching already
  took the money off the table; reopening requires an explicit
  Architect decision. The ROUTER gate — red at the 07-13 decision —
  OPENED 2026-07-21 on the re-registered coordination framing
  (§6.5): the pre-registered leaf-routing experiment took its keys,
  the adopt decision landed as D-0087/D-0088, and the workstream's
  remaining path to closure (and with it Phase 2's) is the first
  live window of judge-based acceptances audited at calibration #4;
  the window itself is already collected (07-22: four judge-basis
  acceptances and five reject verdicts in the journal).
- **Phase 3 (toolkit, D-0070) — CLOSED 2026-07-12:** the system
  packaged as a public installable template (Supervised-Delegation
  v0.1.0), validated by two installs (§4.1); template changes ship
  only as verified batches from the dogfooding deployments (D-0074).
  Batches since: releases v0.4.0–v0.4.2 (2026-07-20) brought the kit
  to parity with the dogfooding deployment — policy kernel, gate
  suite, judge onboarding — with a port queue accumulating between
  operator-opened syncs. The v0.5.0 snapshot is assembled and gated
  behind calibration #4 (operator's word, 2026-07-22).
- **Continuous:** the delegation table and this paper's §7 are living
  documents; Shadow Evaluation runs append to
  docs/SHADOW_EVALUATION_LOG.md; the weekly calibration aggregates
  the journal and owns every status movement (runs #1–#3 done, #2
  moved coding→Middle to rejected; #4 due ~2026-07-25 carries the
  first leaf-routing window audit).

## 11. Limitations

Shadow Evaluation volume is honest but lopsided: 31 judged pairs on
coding (with a recorded caveat — pair-instances repeat prompts
across runs; the largest run held 11 distinct prompts of 19 pairs),
n≈2 everywhere else, and the paid-source reject trend is three days
old — the status movement it implies is deliberately left to the
calibration. provisionally_validated rows rest on a 3.4-day window;
production_validated requires a full week plus a
cost-per-accepted-unit trend that has one baseline point so far.
The subscription baseline remains censored data (it bounds rates,
it cannot refute hypotheses about unconstrained spend). The
C3 = 0.11% measurement covers one API window on one provider's
caching — it closes the workstream locally, not as a general claim.
Exam evidence is n=1 per candidate, and the ranking instrument is
itself a weak ranker (the control's gap equals the pre-registered
threshold); single machine (6 GB VRAM constrains local tiers to 4B);
the judge calibration set is young (13 pairs) and grows only as
fast as chief-judge reviews happen; retry-loop cost is designed into
the method (the `attempt` field exists) but the trend is not yet
measured. The mechanism discipline of §6.2 is ten days old at this
update (2026-07-22); its detectors have fired in production beyond
their motivating incidents (F-34, F-37, F-38) — evidence both that
the net catches and that leaks keep arriving — and the validation
layer above the gates (§6.6) has since been added. The task-pipeline
pilot (the QA conveyor) is live and cycling; its incidents feed the
method back as findings (e.g. the AT-BUG-022 deliverable-drift
incident → F-50 and calibration check 31).

---

*Canonical sources: ARCHITECTURE.md (specification; boot core
ARCHITECTURE_BOOT.md), DECISIONS.md index + docs/DECISIONS_FULL.md
(D-0001…D-0089), DELEGATION_TABLE.md + docs/SHADOW_EVALUATION_LOG.md
(evidence), logs/routing-log.jsonl (routing journal),
docs/FINDINGS.md (F-1…F-50), PROCESS/JUDGE_CALIBRATION_PROTOCOL.md,
PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md, PROCESS/CRITIC_EXAM.md,
docs/RELATED_WORK.md, docs/TASK_CARRIER_EVAL_2026-07-13.md +
docs/tasks/ (task-pipeline workstream), toolkit/ +
github.com/Xartaxana/Supervised-Delegation (the published
template), gateway/ + tools/ (reference implementation).*
