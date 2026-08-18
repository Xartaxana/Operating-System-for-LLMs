# W2b — Карты переноса R11/R2/R13/R4 (авторство designer t-490, приняты Lead 08-18; VERBATIM)

Ключи зафиксированы ДО прогона не-исполнителем (R11 DOC-DISPATCH
WITNESS (i)). Диспатчи узлов W2b-1/3/4/5 цитируют тексты и карты
ОТСЮДА. Карты R1/R8 — §3.2/§3.3 спеки
docs/tasks/2026-08-18_w2b-claude-md-form-spec.md (R8 — с расщеплением
f/g/h по амендменту). Карты R9 и лёгкого батча — досылка designer
перед W2b-7.

Форма карт: `# | утверждение (строки CLAUDE.md) | ключ (verbatim,
фиксирован ДО прогона) | новое место`. Ключ обязан уцелеть дословно
по указанному адресу; исполнитель карту не дописывает — утверждение
без адреса возвращается вопросом.

## 2.1 R11 (строки 250–315; ≈4 320 Б → ≈4 105 Б, −5%)

Новый текст:

```
R11. **DoD in every dispatch (D-0054)**: what "done" means and how
acceptance verifies it, in the tier's form, INLINE in the dispatch
prompt — a bare pointer to a spec file or an earlier event is NOT a
DoD. Next to it — the CONTEXT MANIFEST (D-0073): "given" = enumeration
of injected files/data; a writing dispatch adds owns (ABSOLUTE write
paths) / non-goals / handoff. Completeness of both is the DISPATCHER's
duty BEFORE sending (checklist below); silence on an edge its own
requirements create is a dispatcher defect, not the performer's guess.

| R11 | when | duty | src |
|---|---|---|---|
| a | builder | acceptance criteria + the verification run whose output becomes the witness | D-0054 |
| b | the spec sets a limit/truncation, admits an empty/absent/None input its data can carry, or carries a pair of its own requirements that can conflict | for each, the expected behavior is STATED — or the fork is explicitly handed down as a question | D-0054 |
| c | edge sub-class (i) TEMPORAL — an artifact the change itself brings into existence (a config, file or flag absent at spec time, present after) | the behavior is stated for BOTH worlds, before and after it exists, and the spec says which move creates it | D-0054 |
| d | edge sub-class (ii) POSITIONAL — the spec prescribes WHERE in existing logic a branch goes (order, precedence, before/after which check) | it states the INVARIANT that position must preserve (what stays unreachable, what must still be refused), not the location alone: a position without its invariant is the dispatcher's guess handed to the performer as fact | D-0054 |
| e | the task has an INTERACTIVE surface (CLI/UI taking user input) | the DoD adds an adversarial mini-battery — size, nesting, encoding, empty/broken input; every limit/boundary the code introduces gets a test AT and BEYOND it | D-0054 |
| f | test volume under e | SCOPE CEILING: acceptance keys + battery + boundaries; full regress beyond is not required | D-0054 |
| g | scout | explicit question(s) + a completeness criterion ("X is nowhere" is a valid result requiring a trail) | D-0054 |
| h | critic | the spec/DoD of the reviewed work attached | D-0054 |
| i | a parallel fan-out | ownership per R4 + optional maxConcurrent | D-0073 |
| j | the manifest on READS | DECLARATIVE: reading past the basket is a report line, not a violation; a point read-only dispatch just enumerates its basket inline | D-0073 |
| k | the manifest on WRITES | NORMATIVE | D-0073 |
| l | the owns are markdown/config with no test set of their own (DOC-DISPATCH WITNESS) | a deterministic key-presence run IS a legal mechanical layer, but ONLY with three properties: (i) the keys are quoted VERBATIM from the DoD as written BEFORE the run; (ii) the script is committed as a test OR attached in FULL source with the witness; (iii) the run includes a NEGATIVE control (one key deliberately absent → the script reports failure) | D-0052 |
| m | any of l's three properties is missing | the witness is a retelling, not a run (D-0052 class); detector — check 13(л) | D-0052 |
| n | a checklist miss exposed by a reject or finding | a spec-defect of the dispatcher; promotion to a machine layer follows the next recurrence | D-0063 |
| o | a worker returns a DoD-less dispatch (or a writing/parallel one without a manifest) with questions | the emergency net, not the normal cycle: frequent returns = a spec-discipline defect of the coordinator, a calibration case | D-0054 |

FIVE-POINT CHECKLIST (D-0096), run against every dispatch before it
goes: (1) explicit question / completeness criterion or acceptance
keys; (2) DoD inline with the exact verification run AND the edge
behaviors NAMED — limits/truncations, empty/absent inputs, conflicting
requirement pairs: stated, or explicitly forked down; (3) "given"
enumerated AND sufficient — data, fixtures, paths NAMED, not implied;
(4) writing dispatch: owns/non-goals/handoff present; a PARALLEL
writing dispatch also names the NARROWED witness scope (R4);
(5) freshness — the spec's load-bearing facts checked against their
carrier, not memory (a stale note in the spec is a dispatcher defect;
machine layer — the dispatch_gate given-path warn).
```

Ядро — 8 строк. Чеклист сохранён ДОСЛОВНО отдельным списком (Р1(A)).
Манифест-токены "given", owns (ABSOLUTE write paths) / non-goals /
handoff — в ядре дословно; в чеклисте п.(4) дословно; в строках
реестра токенов нет.

Карта переноса R11:

| # | Утверждение (строки) | Ключ (verbatim) | Новое место |
|---|---|---|---|
| 1 | DoD в каждом диспатче: что значит «сделано» и как приёмка проверяет, в форме яруса (250–251) | `what "done" means and how` | ядро |
| 2 | builder: критерии приёмки + прогон, чей вывод становится witness (251–253) | `the verification run whose output becomes the witness` | R11.a |
| 3 | спека называет КРАЯ: лимиты/усечения, пустой/None вход, конфликтующая пара требований — поведение СФОРМУЛИРОВАНО либо развилка вниз (253–257) | `every pair of its own requirements that can conflict` | R11.b |
| 4 | молчание спеки на крае её же требований — дефект диспетчера (257–258) | `not the performer's guess` | ядро |
| 5 | подкласс (i) ВРЕМЕННОЙ: оба мира + какой ход создаёт (258–263) | `the behavior is stated for BOTH worlds` | R11.c |
| 6 | подкласс (ii) ПОЗИЦИОННЫЙ: позиция → ИНВАРИАНТ (263–268) | `a position without its invariant` | R11.d |
| 7 | ИНТЕРАКТИВНАЯ поверхность → адверсариальная мини-батарея (269–271) | `adversarial mini-battery` | R11.e |
| 8 | каждый лимит/граница — тест НА и ЗА (271–272) | `a test AT and BEYOND it` | R11.e |
| 9 | ПОТОЛОК ОБЪЁМА (272–273) | `SCOPE CEILING` | R11.f |
| 10 | scout: явный вопрос + критерий полноты (273–275) | `"X is nowhere" is a valid result requiring a trail` | R11.g |
| 11 | critic: приложена спека/DoD ревьюируемого (275–276) | `the spec/DoD of the reviewed work attached` | R11.h |
| 12 | МАНИФЕСТ: «given» = перечисление (276–278) | `"given" = enumeration of injected files/data` | ядро (манифест-токен) |
| 13 | пишущий добавляет owns/non-goals/handoff (277–278) | `owns (ABSOLUTE write paths) / non-goals / handoff` | ядро (манифест-токены) |
| 14 | параллельный веер — R4 + maxConcurrent (278–279) | `optional maxConcurrent` | R11.i |
| 15 | манифест ДЕКЛАРАТИВЕН по чтению (279–281) | `reading past the basket is a report line` | R11.j |
| 16 | точечный read-only перечисляет корзину инлайном (281–282) | `enumerates its basket inline` | R11.j |
| 17 | манифест НОРМАТИВЕН по записи (281) | `NORMATIVE on writes` → `| k | the manifest on WRITES | NORMATIVE |` | R11.k |
| 18 | полнота — обязанность ДИСПЕТЧЕРА ДО отправки (282–284) | `the DISPATCHER's duty BEFORE sending` | ядро |
| 19 | пятипунктовый чеклист D-0096 целиком (284–294) | `FIVE-POINT CHECKLIST` + `the dispatch_gate given-path warn` | отдельный список (дословно) |
| 20 | промах чеклиста = spec-дефект; промоция по рецидиву (294–297) | `promotion to a machine layer follows the next recurrence` | R11.n |
| 21 | DoD ИНЛАЙНОМ; голый указатель — не DoD (297–299) | `a bare pointer to a spec file or an earlier event is NOT a DoD` | ядро |
| 22 | ДОКОВЫЙ ВИТНЕСС: три свойства (300–309) | `the keys are quoted VERBATIM from the DoD as written BEFORE the run` | R11.l |
| 23 | нет любого из трёх → пересказ; детектор чек 13(л) (309–311) | `the witness is a retelling, not a run` | R11.m |
| 24 | возврат вопросами — аварийная сеть; частые возвраты = дефект координатора (311–315) | `the emergency net, not the normal cycle` | R11.o |
| — | обоснования краёв и докового витнесса | — | уже дублируется: POLICY_FULL «## R11 — края поведения…rationale» (:767), «## Витнесс доковой…rationale» (:819), «### R11» (:889–903) |

## 2.2 R2 (строки 62–94; ≈2 150 Б → ≈1 995 Б, −7%)

Новый текст:

```
R2. **Implementation to a ready spec → builder**: the Lead writes the
spec; the builder returns missing requirements as questions, never
invents. Acceptance is by witness — the `accepted` event's `witness`
field carries the VERBATIM output of the verification run (command +
result), not a retelling; a report without a witness → `rejected`. The
designer is a STANDING function: spec DRAFTING from a Lead intent
brief, forks returned and never decided silently; the draft passes the
Lead's acceptance before any dispatch uses it.

| R2 | when | duty | src |
|---|---|---|---|
| a | the task's result is a UI | the run includes DRIVING the UI — the witness is a before/after screenshot/recording; a text-only witness is insufficient | D-0052 |
| b | a self-activating enforcement file (hook on the active hooksPath etc.) | is never placed on the path by its builder: it is delivered as content or under a sibling name, and the Lead places it at acceptance | D-0069 |
| c | a WRITING dispatch whose spec carries ≥3 numbered items, or touches ≥3 files | DRAFTING → designer BY DEFAULT, from a Lead intent brief; the Lead self-drafting it anyway is legal ONLY with a `dispatch_skipped` event (agent = designer, reason mandatory) — the same form R1 gives scout | D-0037 |
| d | designer is NOT a cheaper tier than the Lead — same tier OR above | the obligation in c holds anyway: the routing motive is CONTEXT ISOLATION and an independent drafting context, not model price (R8: motive, not price gap) | D-0037 |
| e | below c's threshold, and for intent briefs themselves | the Lead drafts freely with no event; the threshold counts the task's PRIMARY draft | D-0037 |
| f | a RESUBMISSION after a `rejected` — a retry under the SAME task_id | a CONTINUATION of the existing spec: the Lead edits that spec ITSELF, with no designer dispatch and no `dispatch_skipped` event, regardless of the threshold | D-0037 |
| g | work re-badged under a NEW task_id; parts produced after a `decomposable` | a NEW task each, judged against c's threshold on its own | D-0037 |
```

Карта переноса R2:

| # | Утверждение (строки) | Ключ (verbatim) | Новое место |
|---|---|---|---|
| 1 | реализация по готовой спеке → builder; спеку пишет Lead (62–63) | `the Lead writes the` + `spec` | ядро |
| 2 | builder возвращает недостающее вопросами (63–64) | `returns missing requirements as questions, never` | ядро |
| 3 | приёмка по witness: ДОСЛОВНЫЙ вывод, не пересказ; без witness → rejected (64–67) | `carries the VERBATIM output of the` | ядро |
| 4 | UI: вождение UI, «до/после», текст недостаточен (67–69) | `a text-only witness is insufficient` | R2.a |
| 5 | самоактивирующийся файл не кладётся билдером на путь (69–73) | `it is delivered as content or under a sibling name` | R2.b |
| 6 | designer — СТОЯЧАЯ функция; развилки возвращаются (73–75) | `forks returned and never decided silently` | ядро |
| 7 | драфт проходит приёмку Lead до использования (75) | `Lead's acceptance before any dispatch uses it` | ядро |
| 8 | порог: ≥3 пунктов или ≥3 файлов → designer (76–78) | `≥3 numbered items` | R2.c |
| 9 | самодрафт только с dispatch_skipped — форма R1/scout (78–80) | `the same form R1 gives scout` | R2.c |
| 10 | держится и при не-дешёвом дизайнере — тот же ярус или выше (80–82) | `same tier OR` + `above` | R2.d |
| 11 | мотив — изоляция контекста, не цена (82–84) | `CONTEXT ISOLATION and an independent` | R2.d (хвост «not the price gap» → ссылка «R8: motive, not price gap»; норма дословно в ядре R8) |
| 12 | ниже порога и брифы — свободно без события (85–86) | `freely with no event` | R2.e |
| 13 | порог считает ПЕРВИЧНЫЙ драфт (86) | `the task's PRIMARY draft` | R2.e |
| 14 | ПЕРЕСДАЧА под тем же task_id — продолжение спеки, правит Lead сам (86–90) | `a CONTINUATION of the existing spec` | R2.f |
| 15 | новое task_id — новая задача с порогом (90–91) | `re-badged under a NEW task_id` | R2.g |
| 16 | части после decomposable — новые task_id, порог каждой (91–93) | `parts produced after a` + `decomposable` | R2.g |
| 17 | обоснование/пилот/замер — POLICY_FULL (93–94) | — (роль указателя у src) | уже дублируется: POLICY_FULL «## designer — стоячая функция…rationale» (:671) + «### R2» (:853–871) |

## 2.3 R13 (строки 339–368; ≈1 980 Б → ≈2 060 Б, +4% — принято Р9(A))

Новый текст:

```
R13. **Leaf routing (D-0087)**: intake classifies every task — a LEAF
closes under one performer of one allocate-category with no
dependencies; doubt = graph. A leaf runs through the D-construction BY
DEFAULT: category→tier by the ladder, worker executes, acceptance by a
CALIBRATED JUDGE (verdict recorded; `basis: "judge"`), deterministic R6
mirror on reject (one retry same tier → one-step escalation → failed
back to the coordinator); the coordinator stays out of the leaf loop.
Graph tasks keep the standard Lead loop.

| R13 | when | duty | src |
|---|---|---|---|
| a | the coordinator takes a leaf through the standard acceptance path | a deviation: legal ONLY with a recorded reason in the journal; the window detector is check 30 | D-0094 |
| b | recon-leaf intent keys / DoD | carry the NEGATIVE-FORM-CONTROL criterion (command hygiene p.6): a negative claim in the material without its positive same-form control → reject | D-0087 |
| c | which judge is legal | TWO forms: the gateway alias (judge-sonnet, needs a live proxy — the only form for script-driven constructions) and a SUBSCRIPTION judge-subagent carrying the pinned JUDGE_SYSTEM_PROMPT (gateway/shadow_eval.py) VERBATIM; a drifted subagent-judge prompt is a finding, not a judge; with no judge available in either form the standard acceptance path applies | D-0087 |
| d | the dispatch is NOT leaf-class — a mechanism, a policy edit, an integration whole | judge acceptance is illegal: those keep the D-0058 matrix; it is legal ONLY for recon / implementation to a written spec | D-0087 |
| e | a quality-critical task, on the operator's word | H-mode: a Lead-authored DAG + per-node intent keys incl. adversarial probes + D-machinery on leaves | D-0087 |
| f | misclassification | recoverable by construction: a leaf that was really a graph comes back via judge reject / `decomposable` (R5); a graph-classified simple task only pays the Lead-layer tax | D-0087 |
```

Карта переноса R13:

| # | Утверждение (строки) | Ключ (verbatim) | Новое место |
|---|---|---|---|
| 1 | intake классифицирует; ЛИСТ = один исполнитель, одна категория, без зависимостей; сомнение = граф (339–341) | `doubt = graph` | ядро |
| 2 | лист через D-конструкцию по умолчанию (341–343) | `category→tier by the ladder` | ядро |
| 3 | приёмка калиброванным судьёй, basis: "judge" (343–344) | `CALIBRATED JUDGE` | ядро (словарь basis) |
| 4 | зеркало R6: ретрай → эскалация → failed (344–345) | `one retry same tier` | ядро |
| 5 | координатор вне лист-петли (345–346) | `stays out of the leaf loop` | ядро |
| 6 | отклонение — только с записанной причиной; детектор чек 30 (346–349) | `the window detector` + `is check 30` | R13.a |
| 7 | negative-form-control в ключах recon-листа (349–352) | `without its positive same-form control` | R13.b |
| 8 | форма судьи 1: gateway alias, только для скриптовых (352–353) | `the only form for script-driven constructions` | R13.c |
| 9 | форма 2: подписочный судья с пришпиленным промптом (353–356) | `carrying the pinned` + `JUDGE_SYSTEM_PROMPT` | R13.c |
| 10 | дрейфующий промпт — находка, не судья (356–357) | `is a finding, not a judge` | R13.c |
| 11 | замер эквивалентности — POLICY_FULL §R13 (357) | — | уже дублируется: POLICY_FULL «## R13 — Leaf routing…rationale» (:608) + «### R13» (:905–921) |
| 12 | судья только для лист-класса (357–359) | `legal ONLY for leaf-class dispatches` | R13.d |
| 13 | механизмы/политика/интеграция — матрица D-0058 (359–361) | `those keep the D-0058 matrix` | R13.d |
| 14 | графовые — штатная петля Lead (361) | `Graph tasks keep the standard Lead loop` | ядро |
| 15 | H-режим по слову оператора (361–364) | `H-mode` + `adversarial probes` | R13.e |
| 16 | нет судьи в обеих формах → штатная приёмка (364–365) | `With no judge available in either form` | R13.c (хвост) |
| 17 | мисклассификация восстановима по построению (365–367) | `Misclassification is recoverable` | R13.f |
| 18 | граф-классифицированная простая платит налог слоя (367–368) | `pays the Lead-layer tax` | R13.f |

## 2.4 R4 (строки 117–143; ≈1 855 Б → ≈1 955 Б, +5% — принято Р9(A))

Новый текст:

```
R4. **Independent parts → several parallel workers**, each with its own
spec (context isolation). Parallel specs declare path ownership AND the
SCOPE OF THE WITNESS RUN; the Lead checks overlap before launch. Each
worker's verification run is narrowed by OWNS — it must cover the test
sets of all owned paths in that worker's `owns`, not merely the files
the worker judges to be its own (a named narrow target); another
worker's uncommitted state breaks a shared full run. A SOLO writing
dispatch keeps the canonical run.

| R4 | when | duty | src |
|---|---|---|---|
| a | the branches of a parallel batch have converged | the FULL canonical run (`python -m pytest tools/ gateway/ -q`) is the COORDINATOR's duty; its output is APPENDED to the `witness` field of the batch's LAST `accepted` event, which then carries BOTH parts, clearly delimited: first the node's OWN narrowed run, then the canon output labeled BATCH CANON — the canon addition never replaces the node's own proof | D-0052 |
| b | acceptance of a parallel node | stands on its narrowed witness | D-0052 |
| c | a canon failure discovered after convergence | handled as `defect_found` against the responsible node; reopen is forbidden | D-0060 |
| d | parallel SESSIONS in one repo | the same class: never touch or commit another session's uncommitted paths | D-0060 |
| e | a queue item for ANOTHER deploy | exists only if written IN THE SAME MOVE into the carrier the TARGET deploy reads at boot (OS: CURRENT_CONTEXT.md; AO3: docs/HANDOFF.md); own journal notes / FINDINGS are not a carrier — an item living only there is NOT handed over | D-0082 |
| f | a task of ≥5 journal events OR ≥2 sessions | is carried as a markdown DAG in docs/tasks/ (nodes/statuses/tiers; a WRITING node also declares its owns paths); a node's status moves in the same move as its journal event | D-0080 |
```

Карта переноса R4:

| # | Утверждение (строки) | Ключ (verbatim) | Новое место |
|---|---|---|---|
| 1 | независимые части → параллельные воркеры, своя спека у каждого (117–118) | `each with its own` + `spec (context isolation)` | ядро |
| 2 | объявляют владение; Lead проверяет пересечение (118–119) | `the Lead checks overlap before launch` | ядро |
| 3 | объявляют и ОБЛАСТЬ ВИТНЕСС-ПРОГОНА (119–120) | `the SCOPE OF THE WITNESS RUN` | ядро |
| 4 | сужение по OWNS: все owned-пути, не «свои по мнению» (120–124) | `not merely the files` + `(a named narrow target)` | ядро |
| 5 | чужое незакоммиченное рвёт общий прогон (124) | `breaks a shared full run` | ядро |
| 6 | полный канон — обязанность КООРДИНАТОРА после схождения (124–126) | `the COORDINATOR's duty` + триггер «have converged» | R4.a |
| 7 | вывод в witness ПОСЛЕДНЕГО accepted, обе части, BATCH CANON (126–130) | `labeled` + `BATCH CANON` | R4.a |
| 8 | канон не заменяет собственное доказательство (130) | `never replaces the node's own proof` | R4.a |
| 9 | СОЛО-пишущий держит канон (131) | `A SOLO writing dispatch keeps the canonical run` | ядро |
| 10 | приёмка узла на суженном witness (131–132) | `stands on its narrowed witness` | R4.b |
| 11 | провал канона после схождения → defect_found на узел (132–134) | `against the responsible node` | R4.c |
| 12 | параллельные СЕССИИ — тот же класс (134–136) | `never touch` + `or commit another session's uncommitted paths` | R4.d |
| 13 | кросс-деплойный пункт — тем же ходом в носитель целевого (136–139) | `IN THE SAME MOVE into the carrier the TARGET deploy` | R4.e |
| 14 | свои notes/FINDINGS — не носитель (139–140) | `is NOT handed over` | R4.e |
| 15 | ≥5 событий / ≥2 сессий → DAG в docs/tasks/ (140–143) | `carried as a markdown DAG in docs/tasks/` | R4.f |
| 16 | статус узла — тем же ходом, что событие (143) | `moves in the same move as its journal event` | R4.f |
| — | обоснование owns на пишущих узлах DAG | — | уже дублируется: POLICY_FULL «## R4 — owns на пишущих узлах DAG…rationale» (:655) + «### R4» (:873–880) |

НАБЛЮДЕНИЕ дизайнера (доложено, не правка): строки R4.e/R4.f
(D-0082/D-0080) к параллельности отношения не имеют — осели в R4 за
неимением места; перенос сломал бы внешние ссылки (RULE_COVERAGE:53),
оставлены строками реестра.
