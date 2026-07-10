# Supervised Delegation: an Operating System Approach to LLM Cost

**White Paper — living draft v0.2.0 (2026-07-10)**

Status: draft. Every claim in section 7 is backed by repository
evidence (commits, DELEGATION_TABLE.md + docs/SHADOW_EVALUATION_LOG.md,
requests.db, logs/routing-log.jsonl, docs/FINDINGS.md); numbers
will be revised as telemetry volume grows. Deliverable #1 of
PROJECT_CHARTER.md.

Changelog: v0.2.0 (2026-07-10) — full-document revision against the
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
not raw repetition (D-0036).

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
calibration (D-0047), never mid-stream.

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
the one case where reasoning quality mattered.

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
The first weekly calibration — the moment table statuses first move
on this contour — is pending its one-week routed-traffic minimum.

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

## 7. Empirical Status (2026-07-10)

What the evidence currently supports — with honest caveats: Shadow
Evaluation volume is small (n=2 per category), its traffic synthetic,
its "Lead" baseline a free-tier model; the subscription-contour
baseline is CENSORED data (the operator rationed frontier usage);
routing-journal categories are all still `estimated`, awaiting the
first weekly calibration.

API contour (Shadow Evaluation + judge, details in
docs/SHADOW_EVALUATION_LOG.md):

| Claim | Evidence |
|---|---|
| Extraction, formatting, summarization delegate to a 4B local model | Shadow Evaluation, judge-verified, pass_rate 1.00 |
| Routine code generation delegates to Middle (70B) | tier-matching replay, judge pass_rate 1.00, chief-judge review of both pairs |
| Classification does NOT delegate to 4B | judge + manual review agree: flawed reasoning on a mixed-sentiment case |
| difflib similarity is not a verdict | 2 of 5 first-run verdicts were false rejections |
| 70B judge unusable for code pairs | hallucinated bug in correct code, reproduced across independent runs |
| Judge nondeterminism at default temperature | calibration flip 11/11 → 12/13 between consecutive runs |
| Judge capability tracks model hierarchy | 4B: 11/13, 70B: 12/13, 120B: 13/13 on the same pairs |
| Recon does NOT delegate to the available 4B local model | entrance + hardened re-exam 0/7 twice, fabricated citations; local-scout thread closed until a stronger model fits 6 GB VRAM |

Subscription contour (transcript telemetry + routing journal +
exams, 2026-07-07..10):

| Claim | Evidence |
|---|---|
| Cache reads dominate agentic input | 97.6% of input-side tokens are cache reads; accounted cache savings $7,117 on a $1,178 total — provider caching must be measured before any compression is built (D-0036) |
| Frontier burns fastest per turn (censored baseline; spend-share is NOT the metric) | opus $0.264/turn, fable $0.216 vs sonnet $0.063–0.114 (2–4x); success metric fixed as cost per accepted unit + escalation rate (Architect correction) |
| Rubric exams saturate one tier below the target | F-28: builder-tier control passed the Lead-qualification exam with the day's best score |
| The vignette-measurable frontier delta is independent reproduction | ranking exam, 3 runs, pre-registered rubric: Opus 2/2 > Gemini 2.5-flash 1/2 > Sonnet 0/2 on the diagnostic pair; everything else saturates |
| The coordinator is the reality-grounding weak point | F-27/F-29/F-30: narrated timestamps, one-ledger quota wall, calendar-reset assumption — all journaled within one week, defenses now on the execution path (§6.2) |
| Delegation is opt-in: policy must auto-load | F-1: with agents defined but policy not auto-loaded, the Lead did delegable work itself on the most expensive tier |

Supervision cost so far: the judge's accounted spend for the entire
calibration + evaluation history is ~$0.01 against a source traffic
sample accounted at ~$0.03 — trivially satisfying Rule #1 at this
scale, but the ratio only becomes meaningful with production volume.
Scout-tier recon economics are near zero on the subscription contour
($1.33 accounted all-time), so the standing case for cheap recon is
resilience and the API-contour pilot, not savings — recorded to
prevent overclaiming.

Accounting hardening (2026-07-04, since Architect-reviewed): Shadow
Evaluation reads proxy-accounted costs for replay targets and judge
calls (never a silent $0; historical `cost_target=$0.0000` lines are
accounting artifacts), and all traffic is tagged
real/synthetic/replay/judge — Phase 2 gates count only `real`.

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
  an archive the moment it closes, leaving a one-line pointer. Two
  "boot diet" rounds (D-0051, D-0067/68) split decision full-texts
  from the always-loaded index, replaced the full architecture spec
  on the boot path with a session-sized operative core, and made
  the breach response itself an executable procedure (archive sweep
  first; deep cuts of operative documents only by explicit
  Lead+Architect decision). Current boot path: ~84 KB.
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

- **Phase 1 (API contour — MVP complete):** Gateway, Guard, Ledger,
  Analyst and Shadow Evaluation are built and verified (159+ tests
  green on the canonical run). Operationally open: routing real API
  traffic through the gateway and a paid frontier Lead baseline —
  both wait on keys held by the Architect.
- **Phase 1.5 (current — real telemetry and Claude Code routing,
  D-0034):** transcript telemetry is live and cache-aware
  (per-model/per-session/per-agent accounted cost, sidechain
  attribution); the routing MVP is DEPLOYED on two projects with the
  policy Architect-accepted; the routing journal is the evidence
  stream. Next: accumulate ≥1 week of routed traffic, then the first
  weekly calibration (PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md; run
  ends with a journaled `calibrated` event whose staleness the Boot
  Report watches) — the first moment any subscription-contour status
  may legally move.
- **Phase 2 (entered on evidence, D-0029, D-0033, D-0059):** three
  independently gated workstreams, each gate computable from
  existing telemetry (ROADMAP.md holds the thresholds; revising one
  requires a decision-log entry). The ROUTER gate: ≥30 judged pairs
  per category, validated-delegable share ≥25% of Lead spend, stable
  category mix, projected savings ≥3x router cost, and a paid Lead
  or explicit sign-off. The CONTEXT-MANAGEMENT gate (reframed as
  evaluation, D-0036): all criteria measured CACHE-AWARE — the
  driver is confirmed only if PAID UNCACHED re-sent input is ≥25% of
  accounted input spend; provider caching is measured before any
  compression tooling is evaluated. The TASK-PIPELINE gate (D-0059):
  externalize intake → scope → DAG → allocate from the Lead's head
  into artifacts, gated on tasks big enough to drop edges at session
  boundaries; artifacts before code, decomposition authority stays
  with the Lead. A green gate produces a written report and a human
  signature, not an automatic transition; the first task of any
  opened workstream is an evaluation of an existing tool, never a
  build (D-0030).
- **Continuous:** the delegation table and this paper's §7 are living
  documents; Shadow Evaluation runs append to
  docs/SHADOW_EVALUATION_LOG.md; the routing journal accumulates
  toward each weekly calibration.

## 11. Limitations

Shadow Evaluation samples remain small (n=2 per category) and its
traffic synthetic; the API contour has carried no real traffic yet
and its Lead baseline is a free-tier model. The subscription-contour
baseline is censored data (the operator rationed frontier usage), so
it can bound rates, not refute hypotheses about unconstrained spend.
All routing-journal categories are still `estimated`: the first
weekly calibration has not yet run, so the production-evidence loop
this paper describes has completed zero full cycles. Exam evidence
is n=1 per candidate, and the ranking instrument is itself a weak
ranker (the control's gap equals the pre-registered threshold);
single machine (6 GB VRAM constrains local tiers to 4B); the judge
calibration set is young (13 pairs) and grows only as fast as
chief-judge reviews happen; retry-loop cost (the strongest external
counter-datapoint to naive delegation) is designed into the method
but not yet measured locally. The mechanism discipline of §6.2 is
one week old: its own failure detectors are registered but have
fired only on the incidents that motivated them.

---

*Canonical sources: ARCHITECTURE.md (specification; boot core
ARCHITECTURE_BOOT.md), DECISIONS.md index + docs/DECISIONS_FULL.md
(D-0001…D-0068), DELEGATION_TABLE.md + docs/SHADOW_EVALUATION_LOG.md
(evidence), logs/routing-log.jsonl (routing journal),
docs/FINDINGS.md (F-1…F-30), PROCESS/JUDGE_CALIBRATION_PROTOCOL.md,
PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md, docs/RELATED_WORK.md,
gateway/ + tools/ (reference implementation).*
