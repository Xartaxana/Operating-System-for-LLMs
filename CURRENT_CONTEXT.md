# Current Context

## Maintenance Rule (D-0038)

This file holds LIVE state only: the current milestone, the single
authoritative task (D-0025), the queue, condensed system state,
strategic guidance still steering decisions, and operational
environment notes. When a task or workstream CLOSES (review ACCEPTED
or Architect sign-off), the session that closes it moves the spec,
execution report and review VERBATIM to docs/task_reports/ and leaves
a one-line pointer here. Evidence is never deleted, only relocated.
Rationale: this file is loaded on every boot (BOOT.md); boot context
is a paid resource — the project's own subject.

## Current Milestone

Phase 3 — Toolkit (D-0070): система как инструмент для чужих
проектов. Phases 1/1.5 — все шаги закрыты с evidence, закрытие
ПРЕДЛОЖЕНО 2026-07-11 и ждёт подписи Архитектора (блок закрытия в
ROADMAP.md); телеметрические циклы (еженедельная калибровка, тренд
экономии) продолжаются как штатные операции, не фазовая работа.
Plan of record: docs/UNIFIED_PLAN_2026-07-07.md + Phase 3
docs/TOOLKIT_INTAKE_2026-07-11.md.

## Current Task (Authoritative, D-0025)

TOOLKIT, стадия 4 — стройка по спеке ядра. Стадии 1–3 закрыты
2026-07-11: инвентаризация t-044 (в интейке), ответы оператора В1–В6
(в интейке; репо https://github.com/Xartaxana/Supervised-Delegation
создан/пуст/доступен — сверено ls-remote), спека ядра v0 —
docs/TOOLKIT_CORE_SPEC.md (состав шаблона, онбординг одним вопросом
контура + delegation.config.yaml + обязательные экзамены с
override-словом пользователя, контракт уведомлений, EN-перевод как
крупнейший кусок, порядок стройки 1–7). СТАДИЯ 4 ЗАКРЫТА, ПЕРВЫЙ ПУШ ВЫПОЛНЕН 2026-07-11:
github.com/Xartaxana/Supervised-Delegation, main, коммит a0b3cd9
«v0.1.0-pre», 64 файла. Конвейер: t-045..t-050 (перевод/скелет/
скиллы/PROCESS/код) → сборочный critic t-051 (ДОРАБОТАТЬ: 2 блокера
— override-событие несовместимо с валидатором [решение Lead
ПЕРЕСМОТРЕНО: override пишется в DECISIONS.md пользователя], RU в
исполняемых строках) → t-052 фиксы → t-053 zero-Cyrillic свип
(греп по всему бандлу пуст, 311 passed). Ось 7 (ядро ↔ шаблон)
добавлена в SIBLING_MAP тем же ходом (D-0070).

СТАДИЯ 5а ПРИНЯТА 2026-07-11 (t-055): «незнакомец» (сессия
оператора, Sonnet-координатор, полигон D:\Improving_AI\From_Zero;
промпт: docs/toolkit_stage5a_stranger_prompt.md) дошёл до первого
делегированного цикла — журнал/гейты/матрица приёмки на свежей
установке РАБОТАЮТ; отчёт архивирован:
docs/task_reports/2026-07-11_toolkit-stage5a-stranger-report.md.
Все 7 находок шаблона закрыты t-058 (принят). Хвосты дня: (1) t-057 ЗАКРЫТ (att.3 PASS 7/7): ужесточения
scout-правил 3 (запрет суждения) и 4 (позитивный контроль пустого
поиска — класс «ложно-пустой grep», 3 рецидива за день) внесены в
ОБЕ копии роли + гигиена п.6 обоих CLAUDE.md + п.2а протокола
набора (кэш определений агентов: in-session прогон правки роли
невалиден); подтверждающий ШТАТНЫЙ прогон золотого набора — ПЕРВЫМ
ДЕЛОМ следующей сессии; AO3-порт (их scout-правила 3+4 + гигиена + ужесточения builder
«не изобретай» / critic «вердикт ≠ приёмка», F-33) — на следующем
касании их ролевых файлов. (2) РЕЛИЗНЫЙ ПУШ
Supervised-Delegation ждёт явного слова оператора (клон готов в
scratchpad; в пуше: ссылка на репо разработки, фиксы t-058,
ужесточения ролей scout/builder/critic + гигиены, скилл
critic-exam-gen + onboarding/чек-14/карта). (3) Неиспользованный
полигон D:\Improving_AI\fresh-project — удалить после 5б.
(4) CRITIC-ЭКЗАМЕН СОЗДАН И ПРОВЕРЕН (D-0071, приказ оператора):
PROCESS/CRITIC_EXAM.md (протокол+ключи №1+Runs log; прогон №1 на
нашем critic=opus — PASS образцовый, оба капкана независимого
воспроизведения взяты), шаблонный скилл critic-exam-gen принят с
critic-входом (t-059/t-060); ось 8 карты (экзаменационные наборы
ярусов) создана в обеих картах; правило редактора в critic.md
(обе копии), чек 14 обновлён (оба протокола). Затем 5б —
установка в ТРЕТИЙ проект оператора (путь спросить при старте).
После обоих оператор раздаёт шаблон желающим; снятие pre-release =
стадия 6. Лицензия MIT ПОДТВЕРЖДЕНА оператором 2026-07-11 — вопрос
закрыт. ПРИОРИТЕТ ОПЕРАТОРА
2026-07-11: закрытие Phase 2 — ПОСЛЕ первого пуша тулкита;
текстовые задачи для API-builder (builder-groq) забираются по ходу
стройки тулкита. Phase 1/1.5 ЗАКРЫТЫ 2026-07-11 (подпись
оператора «да закрывай», блок в ROADMAP). Прочие нити: вторая калибровка ~07-18;
статья draft-C и White Paper v0.2.0 — у оператора; остаток старой
очереди — on-touch/evidence-gated. Фикс дайджеста (defect_found
ref=t-002): t-054 ПРИНЯТ 2026-07-11 с critic-входом (R1 читает
docs/SHADOW_EVALUATION_LOG.md, R5 без env-негатива; в шаблоне
дефекта нет — перенос D-0067 там не происходил); собрат-писатель
shadow_eval.py + README — t-056 В РАБОТЕ (builder, фон).

Закрыто 2026-07-11 (нарративы дословно —
docs/task_reports/2026-07-11_day-closures.md): ПЕРВАЯ ЕЖЕНЕДЕЛЬНАЯ
КАЛИБРОВКА (18 чеков, 4 строки Claude-контура ->
provisionally_validated, false-accept: lead 2/8 vs воркеры 0/34);
PAID-LEAD BASELINE ($0.0232, урок «микрозадачи вниз не экономят» —
SHADOW_EVALUATION_LOG 2026-07-11); t-040 счётный скрипт чеков 3/13+A4
(зарегистрирован в чеке 13); ретро-свип rule-10(б/г) D-0028..D-0063
(отчёт 2026-07-11_rule10-retro-sweep.md; единственный разрыв D-0040
закрыт чеком 11). Экономический разрез + baseline тренда:
2026-07-11_savings-analysis.md (чек 18).

- A2 remainder, LIVE part — DONE 2026-07-10 (t-037, accepted on
  attempt 3 after 2 tooling rejections + rule-6 escalation):
  builder-Pi recipe VALIDATED live on builder-groq — trimmed toolset
  1,531 prompt tok (measured), explicit maxTokens=1500 cap fits TPM
  8000, NEW harness break found & closed in config (reasoning echo
  Pi↔Groq → reasoning_format:hidden), multi-turn write→edit→bash
  with real structured calls. Recipe + both breaks:
  gateway/PI_HARNESS.md разрывы №3/№5; evidence: journal t-037.
  Observation queued (evidence row 404): t-018 wall counts actual
  tokens vs Groq admission weight — optimistic on fast-turn bursts;
  transient 429 absorbed by litellm retry, harmless; admission math
  in the wall = candidate on calibration evidence (Rule #1).

- t-015 llama-70B re-exam — CLOSED 2026-07-10, verdict FAIL after
  4 attempts (3 tooling quota aborts + attempt-4 capability
  rejection: pseudo tool-call TEXT + fabricated Trail; pipe excluded
  in-window by tools_stream_check PASS; first F-30 measured launch,
  preflight GO on 97,623 headroom). Local-scout thread FULLY closed:
  both Pi-worker candidates failed on the fabrication axis, no
  cheap-recon row enters the table; scout stays on Haiku (7/7 twice
  today). Archived —
  docs/task_reports/2026-07-10_t015-llama70b-exam-closure.md.

Standing reminder for the first calibration: tier-check the D-0059
commit's session per D-0058 (checks 5/6, F-23 context in the archive
above).

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (commit 171078c; closed
  the last open item of Phase 1.5 step 2). Later policy changes
  follow the normal mechanism discipline.
- Evidence stream: logs/routing-log.jsonl (t-001..t-039); Claude-
  контурные строки таблицы provisionally_validated с первой
  калибровки 2026-07-11 (Update Rule 1, D-0047; evidence-блок в
  DELEGATION_TABLE.md).
- Retro baseline AO3 (cc_usage, pre-routing): $276.70 accounted +
  $57.82 sidechain self-correction (Task 6). Weekly loop compares
  cost per accepted unit + escalation rate, NOT frontier share alone
  (Architect correction — see baseline section below).
- First weekly calibration DONE 2026-07-11 (см. Current Task);
  вторая — к ~2026-07-18 (полновесное недельное окно, трендовые
  чеки 10/11 против baseline первого прогона; staleness watched by
  the Boot Report's Last Calibration line, D-0047).
- 2026-07-08 day narrative (interim 18h read, Task 7 closure,
  dead-tier revival, F-1/D-0041/D-0042, first degradation cycle,
  mechanism day F-12..F-16 / D-0044..D-0051): archived —
  docs/task_reports/2026-07-08_routing-dogfooding-day.md.

## System State (condensed, 2026-07-08)

- Phase 0 closed 2026-07-03 (Zero Context Recovery Test passed).
- Phase 1 steps 1-4 built and verified: Gateway (LiteLLM + SQLite
  request log), Guard (daily per-model budgets, warn 80% / refuse
  100%), Ledger (metrics.py digest), Analyst (Qwen3-4B via Ollama
  through the gateway under its own alias).
- Shadow Evaluation (step 5) operational: shadow_eval.py with
  --judge-model, --calibrate, --categories, honest Rule #1 cost
  extraction (proxy-accounted costs; never a silent $0); sampler
  excludes judge/replay traffic. Remaining: traffic volume; paid-Lead
  baseline UNBLOCKED 2026-07-10 (ANTHROPIC_API_KEY live — Environment
  Notes), run scheduled by queue/calibration.
- Judge: judge-groq (groq/openai/gpt-oss-120b, free tier), calibrated
  13/13 at temperature=0, reproduced twice. Protocol:
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (D-0031) — status-changing
  verdicts need chief-judge review; 1-2 random audits per run. No
  local judge on this hardware (Qwen3-4B 11/13, below the 90% bar);
  fallback order: judge-groq > paid API judge > local 4B restricted.
  Second judge judge-gemini (gemini-3.5-flash, 13/13, t-023) —
  cross-family point work only (20 req/day): builder-groq
  self-judging pairs.
- Gemini key role exam DONE 2026-07-10 (t-023/t-024/t-025, operator
  order): pro tiers zero free quota; 3.5-flash Lead-REJECTED
  operationally (20 req/day) -> judge-gemini (full exam confirmed);
  2.5-flash (lead-gemini) 12/13 + B-exam passed -> API-contour
  Lead-baseline CANDIDATE (status moves await weekly calibration).
  Exam difficulty CALIBRATED same day (t-026, operator doubt):
  Sonnet passed the same exam with the day's best score -> exam is
  an ENTRANCE FILTER, not a Lead-tier discriminator (F-28); ranking
  exam BUILT and calibrated same day (PROCESS/LEAD_RANKING_EXAM.md,
  t-028/t-029: weak ranker — control gap = threshold; the one
  vignette-measurable frontier delta is the INDEPENDENT-reproduction
  reflex, K3/K5). Run 3 (t-030, 2026-07-10, operator order):
  2.5-flash took the ranking exam in the clean-of-F-30 condition —
  11/12 no zeros, pre-registered Lead bar PASSED; sits between the
  Sonnet control (10/12) and Opus (12/12); independence micro-rank
  Opus 2/2 > Gemini 1/2 > Sonnet 0/2 (K5 lost the same way as
  Sonnet: re-run from the same executor). CANDIDATE grade
  strengthened (ranking instrument now, not just entrance filter);
  status moves still await production journal + first calibration
  (D-0028/D-0035); caveats: weak ranker, n=1. Evidence:
  docs/task_reports/2026-07-10_gemini-key-role-exam.md +
  docs/task_reports/2026-07-10_ranking-exam-run3-gemini-answers.md +
  LEAD_RANKING_EXAM.md Runs log.
- traffic_kind tagging live: real/synthetic/replay/judge; gate G1
  counts only 'real'. The tag travels via extra_body metadata —
  litellm's metadata= kwarg does NOT reach the wire (verified; see
  comments in sqlite_logger.py / shadow_eval.py).
- Tests: suite 159 passed (2026-07-10 witness, t-019 acceptance;
  canonical form python -m pytest tools/ gateway/ -q).
  gateway/conftest.py isolates every test (tmp DB + full litellm
  callback-list snapshot/restore — restoring litellm.callbacks alone
  is NOT enough, litellm copies the logger into six lists at call
  time).
- requests.db: 199 rows (judge 149, synthetic 50, real 0 — the API
  contour has carried no real traffic yet); cc_usage table alongside
  (11149+ turns of which 1759+ sidechain, idempotent import, both
  transcript layouts, agent_id/agent_type attribution + haiku
  pricing, 0 NULL-cost rows).
- DELEGATION_TABLE.md: 4-state model (D-0035).
  provisionally_validated: coding -> Middle, summarization /
  extraction / formatting -> intern; rejected: classification ->
  intern. Claude Code workstream rows: estimated.
- Delegated Tasks 1, 2, 3, 4, 5, 6, 7: ACCEPTED and archived
  (docs/task_reports/ — see Archive below).

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- $1,177.48 accounted all-time (8747 turns, 79 sessions, 4 projects).
  Per model: sonnet-4-6 $735 / opus-4-8 $206 / fable-5 $198 /
  sonnet-5 $39.
- CACHE READS DOMINATE: 97.6% of input-side tokens are cache reads;
  accounted savings vs uncached $7,117 on a $1,178 total — first
  hard evidence for the D-0036 ordering (measure net-of-cache before
  building any compression).
- G1 LOOKS GREEN RETROACTIVELY: real traffic 20 consecutive days
  (>=14 required). Formal check = Task 3 digest + written gate
  report + Architect signature (D-0033). G2 (judge 13/13) holds.
- SPEND MIX — ARCHITECT CORRECTION (2026-07-07): the baseline is
  CENSORED data (operator rationed frontier usage), so it cannot
  refute "the smartest model burns most". Correct reading — frontier
  burns FASTEST per unit: opus $0.264/turn, fable $0.216 vs sonnet
  $0.063-0.114 (2-4x). Consequences: (a) success metric is cost per
  accepted unit by tier + escalation rate, NOT frontier share;
  (b) the escalation journal measures the true tier boundary; the
  weekly loop watches the recent-window trend, not all-time totals.

## Remaining Lead-tier Queue

- D-0043 sweep remainder — CLOSED 2026-07-10 (AO3 commit 55aea06):
  the sibling-report line added to the 7 QA-pipeline prompts that
  lacked it (3 already carried it; measured by grep, t-032).
  Residual CLOSED same day (operator-authorized scout-touch bundle):
  OS scout.md rule 8 + golden set run t-034 7/7 PASS (Runs log);
  AO3 scout.md rules 7-8 + D-0057 port (their docs/SCOUT_GOLDEN_SET.md)
  — see AO3 commit.
- Local scout / gateway-worker harness evaluation: FULLY CLOSED
  2026-07-10 (t-015 verdict FAIL — see Current Task pointer).
  Standing verdicts: Pi harness ADOPTED for gateway workers (recipe +
  known breaks: gateway/PI_HARNESS.md; survey: RELATED_WORK «Agent
  tool harnesses»); qwen3:4b FAILED entrance + hardened re-exam
  (0/7 x2, fabrication); llama-70B (middle-groq) FAILED attempt 4
  (fabricated Trail, F-14) — no cheap-Pi-worker recon row enters the
  table; local scout CLOSED until a stronger local candidate fits
  6GB VRAM; scout-tier economics ~zero ($1.33 all-time), standing
  case is resilience + the API-contour second pilot needing recon. Pi
  builder profile blocked by builder-groq TPM 8000 vs Pi prompt
  weight — unblock path = prompt-slimming eval (A2 remainder below).
  Full narrative (steps 1-3, t-011/t-012 exams, infrastructure
  lessons): archived —
  docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md.
- GSD Pi adoption plan (operator-ordered deep-dive 2026-07-09;
  facts + mechanism inventory in RELATED_WORK «GSD Pi deep-dive»;
  verdict: EXTRACT mechanisms, do NOT adopt the agent — it would
  replace the Lead coordinator and forfeit the cost-crossover loop
  that is our niche). Items in priority order:
  - A1 zero-tool-call guard (t-017) + A2 quota walls (t-018) — DONE
    2026-07-09, archived with accepted limitations
    (docs/task_reports/2026-07-10_queue-closures-archive.md).
    A2 remainder: offline part DONE 2026-07-10 (t-033), LIVE part
    DONE 2026-07-10 (t-037) — builder-Pi recipe VALIDATED, item
    CLOSED (details in Current Task section above; recipe home:
    gateway/PI_HARNESS.md разрывы №3/№5).
    requests(model,ts) index candidate (Rule #1: only on latency
    evidence — spent_today shares the full-scan cost). Quota-wall
    reconciliation with provider headers — DONE 2026-07-10 within
    t-031 (N3: go_at from probe truth, conservative horizon,
    RECONCILIATION line = both-ledgers delta, F-27 closed in code);
    N4 import-time fail-open and N5+discover_dbs locked-DB loud-fail
    landed same task.
  - A3 dispatch context manifest (Lead-class, mechanism — full
    rule-10 treatment; WHEN: next D-0054/rule-11 touch, not a
    dedicated pass): the dispatch text enumerates the exact
    files/data injected into the worker (GSD UnitContextManifest as
    prior art) — makes inject-vs-recon choices auditable and cuts
    worker context cost.
  - A4 Rule-6 deterministic check — ВЗЯТ В РАБОТУ 2026-07-11: часть
    Current Task (счётный скрипт чеков 3/13, см. выше; уроки
    первого ручного прогона уже в задаче, вкл. ветку
    «тред явно закрыт/superseded» с кейса t-012).
  - A5 witness auto-collection (builder-class; WHEN: unblock
    condition MET 2026-07-10 by t-037, but build only with the
    first REAL builder-Pi work cycle — Rule #1: no wrapper before
    there are sessions to wrap; binding itself decided at
    calibration):
    wrapper runs the canonical pytest form after a Pi builder
    session and attaches verbatim output as a witness DRAFT (GSD
    verification_commands + canonical-verdict-field analog);
    acceptance itself stays with Lead (D-0037).
  - B-series (D-0063 two-layer enforcement, operator-confirmed
    2026-07-09: code guarantees the encounter with a rule, AI
    judges fulfillment in meaning — the selection axis for
    everything above):
  - F-30 defense layers 1-2 BUILT 2026-07-10 (t-027, builder+critic
    conveyor, archived: docs/task_reports/2026-07-10_f30-defense-build.md):
    tools/preflight_quota.py (launch rule in PI_HARNESS §3) +
    tools/session_context.py SessionStart hook (.claude/settings.json,
    now in the gate net; detector = check 13ж). Follow-ups into the
    next builder batch: N3 (go_at ignores probe truth), N4 (import-time
    fail-open hole), N5 (locked-DB guard); provider column in
    sqlite_logger (N1/N2 root, axis 2) — queued, evidence-gated.
    B3 remainder — DONE 2026-07-11 (t-043, см. ниже).
  - B1 journal validator — DONE 2026-07-10 (t-031, builder+critic
    conveyor, D-0069): tools/journal_validator.py + .githooks/
    pre-commit; new by/basis fields documented in CLAUDE.md; check-9
    spec hole (continuation/retry dispatch) found by live use and
    fixed same task. NEW residuals: (a) AO3 log_append.py port of
    by/basis + continuation/retry branches (axis 1); (b)
    usage_report.py loud-fail on locked cc_usage DB (critic
    observation, axis-2 symmetry candidate — Rule #1, on evidence).
  - B2 — FOLDED into A2, closed with it (archived same file as A2).
  - B3 SessionStart hook — DONE ЦЕЛИКОМ 2026-07-11 (t-043,
    builder+critic конвейер: attempt 1 rejected по блокеру критика —
    stdin без санитизации ломал ASCII-инвариант и инжектил строки
    мимо MAX_LINES; attempt 2 принят, 307 passed). Хук печатает:
    NOW/LAST EVENT/открытое окно деградации/калибровку/квоты (t-027)
    + MODEL с ярусом из stdin-входа (D-0056a неминуем; санитизация —
    фикс класса «внешне-источниковая строка вывода») + BOOT BUDGET
    (список из BOOT.md, WARN>90K/BREACH>100K + boot-diet hint).
    Размещение на путь — Lead (D-0069). WARN горит с первого прогона
    (94,281 байт) — материал для handoff чека 4 и следующей диеты.
  - NOT adopted (recorded to stop re-litigating): GSD as
    coordinator (duplicates Lead), auto-mode SQLite state machine +
    crash recovery (inseparable from their runtime; our analog is
    session handoff), supply-chain audit tags (no third-party-dep
    loop in this repo today), WXP (not confirmed in official docs).
- Boot-diet — RESOLVED for now (D-0067, Architect decision
  2026-07-10; morning pass and re-breach history archived —
  docs/task_reports/2026-07-10_queue-closures-archive.md). Round 1:
  archiving pass restored 99,775 < 100KB. Round 2 (D-0067): boot
  reads ARCHITECTURE_BOOT.md (~4KB core; full spec on demand),
  Shadow Evaluation Log relocated to docs/SHADOW_EVALUATION_LOG.md —
  boot path measure recorded in the D-0067 commit. CLAUDE.md
  deliberately untouched (worst win/risk ratio — policy dies out of
  context, F-1/F-9). Standing duty: re-measure at every handoff
  (D-0050 check 4, breach-response ordering fixed 2026-07-10).
- One-time rule-10(б/г) sweep D-0028..D-0063 + охота на
  нераспознанные механизмы — DONE 2026-07-11 (приказ оператора;
  отчёт docs/task_reports/2026-07-11_rule10-retro-sweep.md; итоги —
  см. Current Task выше). Rule-10(a) retro-audit deliberately NOT
  queued: its data stream is cc_usage, covered by calibration
  check 11.
- Evidence-acceptance adoption plan (F-17): stages 1 / 1.5 / 1.6 /
  1.7 / 2 DONE 2026-07-08..09 (D-0052..D-0055, D-0060; stage details
  archived —
  docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md).
  Live residuals: deterministic counting script for checks 3/13
  (Lead spec -> builder AFTER the first manual calibration);
  structured worker-report frames (deferred until dispatch volume,
  Rule #1); builder-groq = CANDIDATE API-contour builder binding —
  next text-shaped cycles dispatch there, binding decided on journal
  evidence (D-0028; self-judging caveat pinned in config.yaml).
  Stage 3 (data-gated: only if first calibration's checks 10/11
  show the context/overhead discipline actually leaks): PreToolUse
  hook as context_budget analog — Lead spec -> builder -> critic per
  rule 3. Do NOT build before that evidence (Rule #1).
- Eval plan, stage 1 — LANDED (D-0052 + D-0057; details archived —
  same file as above). Live residuals: AO3 port of D-0057 (rule +
  set for the three shared tiers on next role-file touch; the 13
  QA-pipeline agents decided separately on pipeline data — axes
  1/6); critic golden set (candidate design: diff with seeded
  defects; build only if calibration shows critic drift, Rule #1).
- Eval plan, stage 2 (needs >=1 week routed traffic): journal's
  accepted tasks as a regression set replayed on the API contour on
  model/price changes; minimum-n / pass^k in DELEGATION_TABLE Update
  Rules (thresholds from first-calibration data); numeric judge-human
  agreement in JUDGE_CALIBRATION_PROTOCOL. NOT taken: per-PR CI, full
  execution-based bench harness (Rule #1).
  - Batch API candidate (added 2026-07-10, operator-approved):
    judge/replay/golden-set traffic = independent request sets with
    no latency need — exactly the Message Batches profile (-50% on
    input AND output tokens; most batches <1h, SLA 24h; results keyed
    by custom_id; Groq/Gemini have analogs). TRIGGER (Rule #1, build
    nothing before): ANTHROPIC_API_KEY lands AND stage-2 regression
    replays run regularly — free-tier judge traffic gains $0 from the
    discount today. At adoption: batch endpoints bypass the proxy's
    request logging — the accounting path into requests.db must land
    in the same move (axis 2, never a silent $0). Interactive/agent
    sessions stay off batch by nature (dependent-call loops).
- AO3 session-handoff skill — DONE 2026-07-10 (t-021, AO3 commit
  0911cf6), archived
  (docs/task_reports/2026-07-10_queue-closures-archive.md).
- AO3 CLAUDE.md boot-diet trim + three ports — CLOSED 2026-07-10
  (AO3 commit 55aea06, recon t-032): D-0066 two-pass surveys into
  their rule 1, F-30 extension into their hygiene rule 6,
  breach-response ordering into their handoff check 4. Trim verdict:
  NOT NEEDED — measured narrative share ~1.3KB of 33.2KB, no
  material cut available (Rule #1); their check-4 budget watch
  stands.
- OpenClaw adoption plan (survey 2026-07-10, t-022 + Lead second
  pass — first D-0066 application; facts and full plan: RELATED_WORK
  «OpenClaw survey»). No standalone builds; each item rides an
  already-queued vehicle: (1) per-file boot-budget breakdown (raw vs
  injected + truncation flag, `/context list` as prior art) — into
  session-handoff check 4 on next skill touch AND into B3
  SessionStart hook when built; (2) quota-wall reconciliation with
  provider-reported rate-limit headers (Groq) — TRIGGER FIRED
  2026-07-10 (t-015 attempt 3 / F-27: wall saw 14k, Groq 90.6k —
  side-DB t013.db invisible to it); build with the next builder
  batch, natural pair with B1; EXTENDED per F-30 design
  (2026-07-10): launch recipe for quota-bounded runs goes THROUGH
  a pre-flight script that measures (provider probe + both-ledgers
  sum, F-27 math) and REFUSES on shortfall — launching on an
  unmeasured assumption becomes impossible by construction (D-0063
  code-on-path; three t-015 aborts are the evidence); (3) lane-contract
  fields (Owns/Non-goals/Handoff) — into the A3 dispatch manifest
  template when A3 lands. Recorded as prior art, no work: strict
  selection (validates t-018 no-fallback), two-stage failover +
  cooldown ladder (design ready if a second Groq/Gemini key appears),
  gateway-process cron with per-job model (design source for the
  batch-Lead mode if operator wants it mechanized). NOT adopted:
  channels, delegate identity, compaction/memory (harness-owned),
  utilityModel (duplicates D-0062 function→model).
- Habr article thread (t-036, 2026-07-10): blind A/B done — A=Sonnet,
  B=Opus, operator verdict B>A, neither publishable (role confusion,
  over-enumeration; the selection-of-main-points step was done by NO
  model — Lead/operator work). draft-C written by Lead, role fixes
  v2 (d3e52d2) after operator findings → F-31 registered, policy
  vocabulary section rewritten on both deploys (f5260e4 / AO3
  5e80b93). NEXT: operator writes the final article based on
  docs/draft-C.md and hands it to Lead for proofreading (fact-check
  vs repo, roles, slop patterns) + comparison against the three AI
  drafts. Brief + all drafts: docs/ARTICLE_BRIEF_2026-07-10.md,
  docs/draft-{A,B,C}.md.
- White Paper: v0.2.0 FULL REVISION done 2026-07-10 (operator order:
  beyond the three queued items, sweep the whole document against
  progress since v0.1) — abstract two-contour, §2 cache nuance, §4.1
  Two Vocabularies (D-0062), §5 4-state (D-0035), §5.1 deployed MVP
  + typed journal + D-0058 matrix, §6 second judge + F-28 + ranking
  exam, NEW §6.2 coordinator-as-supervised-worker (F-27/29/30,
  D-0063, degradation), §7 refreshed both contours, §8 boot
  economics + handoff symmetry, §9 harness surveys, §10 Phase 1.5 +
  three gates, §11 honest new caveats. AWAITING Architect review of
  the updated version (operator will review v0.2.0 directly; v0.1.x
  review thread superseded).

## Environment Notes (this machine)

- Ollama 0.31.1 (winget); NVIDIA driver 582.28 — Qwen3-4B runs 100%
  on the GTX 1060 GPU (~5 s warm vs ~15 s CPU).
- Proxy must be started from gateway/ (callback imports are
  cwd-relative). litellm does NOT auto-load gateway/.env — export
  GEMINI_API_KEY / GROQ_API_KEY before starting the proxy.
- lead-gemini = gemini/gemini-2.5-flash (10 req/min, 250 req/day);
  judge-gemini = gemini/gemini-3.5-flash (5 req/min, 20 req/day
  rolling — pace >=13s, point work only). ZERO free quota on this
  key: 2.0-flash and ALL pro tiers (3.1-pro/3-pro/2.5-pro) — 429,
  don't use (probed 2026-07-10).
- ANTHROPIC_API_KEY LIVE since 2026-07-10 (operator purchased key +
  credits; key was added to gateway/.env bare — var name fixed same
  day): lead-sonnet verified end-to-end through the proxy (200,
  14 tok, cost_usd computed, requests.db row 407); lead (Fable) and
  lead-sonnet aliases operational. Credits are prepaid and expire
  12 months from purchase; auto-reload off.
- Free-telemetry mode: intern/analyst (Ollama) carry synthetic
  Haiku-class accounting prices, so Guard/Ledger money paths work at
  $0 cash.
- Operational item CLOSED 2026-07-10: ANTHROPIC_API_KEY live (see
  above) — the "paid Lead" blocker on Shadow Evaluation's paid-Lead
  baseline and on gate R5 is gone; the runs themselves are scheduled
  by the calibration/queue, not started ad hoc.
- BSOD 2026-07-09 15:02 (bugcheck 0x3B in aehd.sys — Android
  Emulator Hypervisor Driver, minidump 070926-7359-01.dmp) while
  the AO3 pipeline exercised the emulator; gateway/Pi processes were
  idle userspace (no intern request had reached the proxy). Rule of
  thumb recorded: do NOT run the Android emulator (AO3 QA pipeline)
  and local GPU inference (Ollama exam runs) simultaneously on this
  machine; sequence heavy workloads. The AO3 session died with
  uncommitted work — its next boot must record the dirty tree per
  Boot Report rule 6.

## Archive (D-0038 pointer)

Closed work lives in docs/task_reports/ — the annotated index is its
README.md (single owner since 2026-07-10; per-file descriptions were
duplicated here and are trimmed from the boot path).

This file is intended to be updated frequently.
