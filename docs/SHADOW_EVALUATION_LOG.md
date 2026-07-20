# Shadow Evaluation Log

Evidence for DELEGATION_TABLE.md Update Rule 1 — one line per Shadow
Evaluation run. Relocated VERBATIM from DELEGATION_TABLE.md
2026-07-10 (D-0067, boot diet round 2: the table stays in the boot
path, closed run history does not). NEW runs append HERE; a table
status change cites its evidence line in this file.

## Evidence block for the 2026-07-11 status moves (relocated VERBATIM from DELEGATION_TABLE.md 2026-07-16, boot diet, same D-0067 home)

Evidence for the 2026-07-11 status moves (Update Rule 1) — first
weekly calibration, `calibrated` journal event 2026-07-11, window
2026-07-08..11 (~3.4 days, real routed traffic, small volume — hence
provisionally, NOT production): scout-haiku 14 accepted / 1
tooling-rejected / 0 defect_found + golden set 7/7 x3; builder-sonnet
11 window dispatches, all acceptances witness-backed, rejects 2x
spec-class (one was a Lead spec error), 0 capability fails, 0
defect_found; critic-opus 9 dispatches, 7 verdicts accepted, findings
repeatedly confirmed by Lead spot-checks (t-001/t-009/t-031); Lead
row confirmed from the failure side — both window defect_found
events sit on the coordinator itself (F-29 ts, t-029 duplicate) and
the F-22 incident shows below-Lead coordination self-certifying.
production_validated requires a full-week window + cost-per-accepted-
unit trend (second calibration).

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

PAID-LEAD BASELINE (2026-07-11, авторизован первой еженедельной
калибровкой; первый прогон с ПЛАТНЫМ источником): рабочий набор
ids 15-24 (10 промптов, 5 категорий) прогнан на lead-sonnet
(rows 408-417, traffic_kind=synthetic, $0.0170), затем replay на
tier-matching цели. Полная стоимость прогона $0.0232 учётно
(24 запроса: 10 synthetic + 7 replay + 7 judge). Категории
classification (строка rejected) и summarization (Junior не
привязан в этом деплое — записанное различие D-0062) не гонялись.

- 2026-07-11  category=coding  source=lead-sonnet target=middle-groq  n=2  sim=0.38  judge=judge-groq pass_rate=0.50  cost_source=$0.0040 cost_target=$0.0002 judge_cost=$0.0004  -> rejected [n=2; статус строки НЕ двинут — Update Rule 1, решает вторая калибровка]
- 2026-07-11  category=extraction  source=lead-sonnet target=intern  n=2  sim=0.83  judge=judge-groq pass_rate=1.00  cost_source=$0.0009 cost_target=$0.0012 judge_cost=$0.0002  -> rejected [КАЧЕСТВО эквивалентно; rejected по Rule #1-ветке кода: учётная цена intern ВЫШЕ платного соннета]
- 2026-07-11  category=formatting  source=lead-sonnet target=intern  n=2  sim=0.91  judge=judge-groq pass_rate=1.00  cost_source=$0.0007 cost_target=$0.0009 judge_cost=$0.0001  -> rejected [та же Rule #1-ветка]

STAGE-2 ЦИКЛ №1 (2026-07-13 ночь, приказ оператора «R1 сначала»;
конвейер t-082..t-085, коммит d90cd03): регрессионный набор из 15
принятых builder-задач (gateway/regression_set_coding.jsonl, все
category=coding по построению) прогнан на lead-sonnet (15 строк
921-939, synthetic, ~$0.68 — ответы 4-17k токенов), реплеи ниже.
Оба прогона ДО category-фикса t-085: эвристика categorize()
раскидала 15 coding-промптов как coding=6/formatting=5/extraction=1/
other=3, отсюда малые n при полном наборе. 15 РАЗЛИЧНЫХ промптов;
прогоны сэмплируют случайные подмножества — пары между прогонами
могут повторять промпт (решение Lead в журнале t-085: инстанс
пары на прогон легален, различимость промптов — этой строкой).

- 2026-07-13  category=coding  source=lead-sonnet target=middle-groq  n=2  sim=0.30  judge=judge-groq pass_rate=0.50  cost_source=$0.0444 cost_target=$0.0007 judge_cost=$0.0007  -> rejected [прогон 1, sample 8 до category-фикса; статус НЕ двинут — Update Rule 1]
- 2026-07-13  category=coding  source=lead-sonnet target=middle-groq  n=4  sim=0.09  judge=judge-groq pass_rate=0.00  cost_source=$0.0577 cost_target=$0.0008 judge_cost=$0.0012  -> rejected [прогон 2, sample 15; middle-groq провалил все 4 — третий подряд reject-сигнал по строке coding->Middle; статус двигает калибровка ~07-18]
- 2026-07-13  category=coding  source=lead-sonnet target=middle-groq  n=19 (distinct prompts=11)  sim=0.07  judge=judge-groq pass_rate=0.05  cost_source=$0.0917 cost_target=$0.0010 judge_cost=$0.0013  -> rejected [прогон 3, sample 30/days 1 — первый полный выход через ground-truth category (конвейер t-082..t-085 на живом прокси, source-перепрогон id 1121–1137); 18 WORSE / 1 EQUIVALENT / 2 пустых ретрая; ЧЕТВЁРТЫЙ подряд reject-сигнал]

Stage-2 цикл №1 ЗАВЕРШЁН 2026-07-13 днём: счёт R1 coding = 31
пара-инстанс / 6 прогонов при пороге >=30/>=2 — объём НАБРАН.
Оговорка для калибровки ~07-18: пары-инстансы включают реплеи
одинаковых промптов между прогонами (в прогоне 3 различных
промптов 11 из 19; решение Lead — журнал t-085), калибровка
взвешивает. Направление evidence одностороннее: 4 reject-прогона
подряд — кандидат-вердикт строки coding->Middle = rejected,
статус двигает калибровка (Update Rule 1).

Chief-judge review прогона 3 (Lead Fable, 2026-07-13, D-0031 — 2
аудита): EQUIVALENT-выброс id 1210 — ЗАЩИТИМ (кандидат выполняет
все явные требования задачи _extract_cost: порядок приоритетов,
DB-fallback, явный None, тесты трёх путей; имя таблицы задачей не
задано — расхождение legal); WORSE id 1179 — ПОДТВЕРЖДЁН (тесты
кандидата сломаны как написаны: нет import sqlite3 в тест-файле;
`"response_cost" in Mock()._hidden_params` бросает TypeError на
входах его же тестов при требовании «never raise»; путь 1 не
обёрнут try).

Chief-judge review (Lead Fable, 2026-07-11, D-0031 — вердикты
статусной силы + 2 случайных аудита):

- coding/409 WORSE — ПОДТВЕРЖДЁН, и это НЕ исторический
  strictness-кейс: middle-groq выдал самосогласованный, но
  нестандартный индекс (F(1)=0; его же пример печатает «10-th = 34»,
  обе канонические конвенции дают 55) — реальный off-by-one против
  общепринятого определения, fibonacci(0) падает. Прослежено
  построчно (n=3/4/5 корректны В ЕГО конвенции — дефект именно в
  выборе конвенции, не в цикле).
- Аудит 412 (extraction) EQUIVALENT — защитим: intern сохранил
  «3.7 million» строкой, соннет нормализовал в 3700000; без заданной
  схемы обе экстракции легальны. Аудит 428 (formatting) EQUIVALENT —
  подтверждён (таблицы идентичны с точностью до регистра).

ГЛАВНЫЙ УРОК прогона (материал второй калибровки и White Paper):
на микрозадачах ПЛАТНЫЙ frontier-источник оказался ДЕШЕВЛЕ
делегирования — короткие ответы соннета стоят меньше, чем
многословный локальный intern по синтетическим Haiku-ценам
(D-0032: бесплатное ≠ $0). Прежние validated-вердикты этих
категорий получены при БЕСПЛАТНОМ источнике (lead-gemini), где
экономика выглядела иначе; строки таблицы получили первый
контр-datapoint с платным источником. Статусы НЕ двигались этим
прогоном (Update Rule 1: движения — на калибровке, с объёмом
n>2 и полной стоимостью с ретраями по Update Rule 4).

MIDDLE-КАНДИДАТЫ (2026-07-13 день, приказ оператора после 4х
reject llama: два новых алиаса middle-oss=gpt-oss-120b и
middle-gemini=gemini-2.5-flash, коммит d91ec9b; тот же
регрессионный набор 15 coding-промптов, source-строки lead-sonnet
id 1121–1137):

- 2026-07-13  category=coding  source=lead-sonnet target=middle-oss  n=11 (distinct=10)  sim=7%  judge=judge-gemini pass_rate=0.27  cost_source=$0.1023 cost_target=$0.0018 judge_cost=$0.0203  -> НЕВАЛИДЕН, F-39 [прогон A: 7/11 ответов обрезаны стендом ровно на 3072 completion-ток. (replay без max_tokens, потолок провайдера; source 4.1–19.5k) — судья мерил стенд; на НЕОБРЕЗАННОМ подмножестве 2/4 EQUIVALENT = 50%. Повтор после фикса t-091; judge-gemini квота 15/20 выбрана — повтор завтра]
- 2026-07-13  category=coding  source=lead-sonnet target=middle-gemini  n=10 (distinct=10)  sim=4%  judge=judge-groq pass_rate=0.50  cost_source=$0.0886 cost_target=$0.0319 judge_cost=$0.0016  errors=4  -> ниже порога, НО с оговоркой F-40 [прогон B: реплеи чистые (без обрезки, до 19.6k ток.); 4 из 10 пар НЕ СУДИМЫ — judge-groq TPM 8000 отверг судейские промпты 9–14k («Request too large»), unjudged-пары — ДЛИННЫЕ, отказ судьи коррелирует с полнотой кандидата; судимое подмножество 3 EQUIVALENT / 3 WORSE]

Chief-judge review обоих прогонов (Lead Fable, 2026-07-13, D-0031
— по 1-2 аудита): прогон A: EQUIVALENT id 1562 (_extract_cost) —
ЗАЩИТИМ (все 3 пути + 4 pytest-теста, import sqlite3 в тестах
присутствует — та самая ловушка llama из аудита прогона 3; имя
таблицы задачей не задано, расхождение legal); WORSE id 1564
(savings_report) — вердикт формально верен, но причина —
ОБРЕЗКА СТЕНДОМ (ответ оборван на середине seed-кода тестов;
требования (c)/(d) до обрыва покрыты) — отсюда F-39 и инвалидация
прогона. Прогон B: EQUIVALENT id 1585 (conftest) — ЗАЩИТИМ
(autouse-фикстура, LIFO через monkeypatch, все 4 колбэк-атрибута,
ответ полный). ПРЕДВАРИТЕЛЬНЫЙ сигнал (не статус): оба кандидата
кратно сильнее llama (5%) на том же наборе; middle-gemini — лучший
из бесплатных (50% на судимом подмножестве при чистом стенде).
Честный полный прогон обоих — после фикса t-091 (max_tokens) и
решения по судейской ёмкости (F-40); статусы двигает калибровка
~07-18 (Update Rule 1).

Фикс t-091 ВЕРИФИЦИРОВАН живыми пробами (2026-07-13 14:35-14:37,
без судьи — difflib-режим, судейская квота не тронута; условия
C1/C2 критика t-091): принудительный --max-tokens 512 -> оба
реплея ровно 512 ток., truncated=2 (живой Groq/gpt-oss отдаёт
finish_reason==length, детектор считает — mock-only риск F-38
закрыт); авто-режим -> truncated=0, ответы 3472 и 4591 ток. — ВЫШЕ
старого потолка 3072 (id 1604-1610). Условие C3 (рост unjudged на
полноразмерных парах) наблюдается в честном повторном прогоне:
A (middle-oss + judge-gemini) — завтра по ролловой квоте судьи;
B-длинные пары — после решения F-40.
- 2026-07-14  category=coding  source=lead-sonnet target=middle-oss  n=6  sim=0.00  cost_source=$0.1281 cost_target=$0.0000  errors=6 truncated=0  -> estimated

Поправка к записи 2026-07-14 (внесена тем же ходом, defect_found
ref=t-091 в журнале): строка выше НЕВАЛИДНА как сигнал качества —
0/6 пар реплеены (errors=6/6), judge-gemini НЕ вызван ни разу
(квота нетронута), verdict "estimated" — код-fallback пустого
прогона, не суждение. Причина ОТЛИЧАЕТСЯ от F-39 (та была
truncation при отсутствующем потолке): здесь t-091's авто-режим
max_tokens (source completion_tokens*1.3, floor 8192) САМ ПО СЕБЕ
превышает TPM-потолок 8000 этой Groq-организации для
openai/gpt-oss-120b на КАЖДОЙ строке — все 15 сохранённых
lead-sonnet coding-строк (id 1121-1137) несут completion_tokens
4138-19537, значит floor 8192 срабатывает всегда и всегда >8000.
Структурно: middle-oss на этом Groq-тире НЕ МОЖЕТ завершить ни
одного авто-режим реплея этого набора, независимо от паузы/сэмпла
(проверено логами прокси: RateLimitError "Request too large ...
Limit 8000, Requested 8421-21148" на всех 18 попытках/6 пар с
2 ретраями каждая). Явный --max-tokens override ниже 8000 обошёл
бы TPM, но возвращает риск truncation (7/15 строк набора >6000
completion-ток.) — то самое напряжение, которое t-091 закрывал.
Решение (override-потолок vs. вердикт «middle-oss инфра-непригоден
на этом Groq-тире для coding») — в очередь калибровки ~07-18 рядом
с coding->Middle (журнал defect_found + CURRENT_CONTEXT).

ЗАКРЫВАЮЩАЯ ЗАПИСЬ КАЛИБРОВКИ №2 (2026-07-18, Update Rule 1,
событие calibrated в журнале): строка «Routine code generation ->
Middle» ДВИНУТА provisionally_validated -> REJECTED на текущих
Middle-привязках. Основание: 4 reject-прогона подряд с ПЛАТНЫМ
источником (07-11 n=2 pass 0.50; 07-13 n=2 pass 0.50, n=4 pass
0.00, n=19/distinct=11 pass 0.05 — реальные принятые
builder-задачи); объём R1 31 пара-инстанс / 6 прогонов >= порога
30/2; оговорка distinct=11/19 взвешена — даже по одним distinct
направление одностороннее. Прежние validated — бесплатный источник,
n=2 микрозадачи (контр-datapoint зафиксирован 07-11). Сопутствующие
решения той же калибровки: (1) middle-oss — вердикт
ИНФРА-НЕПРИГОДЕН на этом Groq-тире (TPM 8000 < floor 8192
авто-max_tokens на каждой строке набора; override возвращает
truncation-риск F-39 — не берём); (2) F-40 (судейская ёмкость
judge-groq на длинных парах): систематический прогон НЕ назначается
(категория rejected); точечные длинные пары при будущем прогоне —
judge-gemini (20 req/day). Возврат строки в estimated — только с
НОВОЙ Middle-привязкой (сигнал middle-gemini 50% на судимом
подмножестве записан, статуса не имеет).
VALIDATED_DELEGABLE_CATEGORIES обновлён тем же коммитом (чек 12).

Table-side note (relocated VERBATIM from DELEGATION_TABLE.md by
boot-diet 2026-07-18; оригинал стоял под evidence-блоком 07-11):

2026-07-18 status move (calibration #2, Update Rule 1): "Routine
code generation -> Middle" provisionally_validated -> REJECTED on
the current Middle bindings — 4 consecutive reject runs with a PAID
source (pass_rate 0.05–0.50 on real accepted builder tasks; R1
volume 31 pairs / 6 runs vs >=30/2), middle-oss ruled
infrastructure-unfit on this Groq tier (TPM 8000 < auto max_tokens
floor), earlier "validated" evidence was free-source n=2
microtasks. Row may return to `estimated` on a NEW Middle binding
(middle-gemini 50% on judged subset is a signal, not a basis —
F-40 judge capacity unresolved). Evidence lines:
docs/SHADOW_EVALUATION_LOG.md (2026-07-11..14 runs + closing entry
2026-07-18). VALIDATED_DELEGABLE_CATEGORIES (gateway/metrics.py)
updated same commit per check 12.

### SHADOW-REPLAY D-0080 п.3 (2026-07-18, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-18  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.0824 judge_cost=$0.0312  truncated=1
- 2026-07-18  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.0824 judge_cost=$0.0140  truncated=1
- 2026-07-18  shadow-replay  task=4 commit=9f31cda72d103a598b427fa8eacb353ae2b71d94 kind=docs-edit  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.0099 judge_cost=$0.0046  truncated=0
- 2026-07-18  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1201 judge_cost=$0.0097  truncated=1
- 2026-07-18  shadow-replay  task=7 commit=d91ec9bf83cc009c05f0ec46d509274849cff344 kind=config  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.0447 judge_cost=$0.0092  truncated=0
- 2026-07-18  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1042 judge_cost=$0.0152  truncated=1
- 2026-07-18  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1210 judge_cost=$0.0111  truncated=1
- 2026-07-18  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1168 judge_cost=$0.0057  truncated=1
- 2026-07-18  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=8  equivalent=1/8  judge=judge-gemini  cost_target_total=$0.6815 judge_cost_total=$0.1007  errors=0 truncated=6

КАВЕРАТ ПРОГОНА (Lead, тем же днём): (1) truncated=6 — шесть worse-
вердиктов выше НЕВАЛИДНЫ как сигнал качества (класс F-39: судья
мерил обрезку стенда при max_tokens=8192 на задачах «файлы целиком»);
честный сигнал первого захода — только пары с truncated=0: task=4
equivalent, task=7 worse. Перепрогон шести — блок ниже (--max-tokens
32000). (2) Судья НЕ калиброван на паре «git-дифф vs полный файл»
(N2 критика t-180) — вердикты совещательные до chief-judge аудита;
аудит-строки ниже. (3) Интерпретационная оговорка (вопрос оператора
07-18): equivalent ≠ «надо было делегировать» — прогон меряет только
СПОСОБНОСТЬ яруса; накладные диспатча (спека/передача/приёмка —
главный едок по экзаменам №5–№10) в вердикте не учтены; сведение
способность × накладные — за калибровкой, практический вывод при
equivalent-классах — БАТЧИНГ мелочей, не поштучная передача.

### SHADOW-REPLAY D-0080 п.3 (2026-07-18, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-18  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.0980 judge_cost=$0.0259  truncated=0
- 2026-07-18  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.1293 judge_cost=$0.0257  truncated=0
- 2026-07-18  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.2693 judge_cost=$0.0395  truncated=0
- 2026-07-18  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.1749 judge_cost=$0.0190  truncated=0
- 2026-07-18  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.3343 judge_cost=$0.0356  truncated=0
- 2026-07-18  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.2514 judge_cost=$0.0309  truncated=0
- 2026-07-18  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=6  equivalent=5/6  judge=judge-gemini  cost_target_total=$1.2572 judge_cost_total=$0.1766  errors=0 truncated=0

CHIEF-JUDGE РЕВЬЮ ПРОГОНА (Lead Fable, 2026-07-18, D-0031 — 3
аудита по requests.db id 1646/1650/1668):
- task=4 equivalent — ПОДТВЕРЖДЁН (баннер удалён, README сохранён).
- task=7 worse — формально верен, но ИСКЛЮЧЁН из сигнала
  способности: промпт корпуса не назвал, КАКИЕ алиасы добавлять
  (имена остались в соседней колонке корпус-дока) — вердикт мерит
  недоопределённость промпта, не модель. Урок корпусу.
- task=15 equivalent — ОСПОРЕН: target дал ядро фикса (PostToolUse
  +PowerShell, ветка dod_track/COMMAND_TOOL_NAMES — проверено по
  ответу id 1668), но НЕ расширил PreToolUse-matcher на Agent —
  несущую часть фактического диффа; промпт Agent тоже не называл
  (второй экземпляр класса task=7) + судейский недосмотр различия.
ЧЕСТНЫЙ ИТОГ ПРОГОНА (обе волны, с аудитом): из 8 кандидатов —
equivalent подтверждённых/неоспоренных 5 (task 2,4,5,11,12), worse 1
(task=1 — крупнейшая работа корпуса, счётный скрипт), оспорен
аудитом 1 (task=15, частичное выполнение), исключён дефектом
промпта 1 (task=7). Полная цена измерения: target $1.94 + judge
$0.28 (обе волны). ИНТЕРПРЕТАЦИЯ — для калибровки №3, с оговоркой
(3) каверата выше: сигнал «Sonnet держит большинство мелких
Lead-самоисполнений по качеству» НЕ равен «поштучная передача
окупается»; практический кандидат-вывод — батчинг мелочей;
класс-урок корпусов: replay-промпт обязан нести ВСЮ спецификацию
задачи (2/8 промптов недоопределены — оба «worse/оспорен»
артефактно).

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.0824 judge_cost=$unknown  truncated=1
- 2026-07-20  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.0824 judge_cost=$unknown  truncated=1
- 2026-07-20  shadow-replay  task=4 commit=9f31cda72d103a598b427fa8eacb353ae2b71d94 kind=docs-edit  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-groq cost_target=$0.0099 judge_cost=$0.0004  truncated=0
- 2026-07-20  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-groq cost_target=$0.1201 judge_cost=$0.0006  truncated=1
- 2026-07-20  shadow-replay  task=7 commit=d91ec9bf83cc009c05f0ec46d509274849cff344 kind=config  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-groq cost_target=$0.0469 judge_cost=$0.0006  truncated=0
- 2026-07-20  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-groq cost_target=$0.1042 judge_cost=$0.0009  truncated=1
- 2026-07-20  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-groq cost_target=$0.1210 judge_cost=$0.0010  truncated=1
- 2026-07-20  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-groq cost_target=$0.1168 judge_cost=$0.0009  truncated=1
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=8  equivalent=2/8  judge=judge-groq  cost_target_total=$0.6836 judge_cost_total=$0.0043  errors=2 truncated=6

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.1441 judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.1353 judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.2737 judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.1824 judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$0.2906 judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-groq cost_target=$unknown judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=6  equivalent=0/6  judge=judge-groq  cost_target_total=$1.0261 judge_cost_total=$0.0000  errors=6 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1283 judge_cost=$0.0457  truncated=0
- 2026-07-20  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-gemini cost_target=$0.1837 judge_cost=$0.0277  truncated=0
- 2026-07-20  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.2982 judge_cost=$0.0392  truncated=0
- 2026-07-20  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.1648 judge_cost=$0.0196  truncated=0
- 2026-07-20  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.2935 judge_cost=$0.0303  truncated=0
- 2026-07-20  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-gemini cost_target=$0.2582 judge_cost=$0.0331  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=6  equivalent=4/6  judge=judge-gemini  cost_target_total=$1.3266 judge_cost_total=$0.1957  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=claude-opus-4-8, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=1 commit=3243e0e353eae45e7d89d195d5a0f3293b001887 kind=script  source=git-lead target=claude-opus-4-8  verdict=worse  judge=judge-gemini cost_target=$0.1892 judge_cost=$0.0428  truncated=0
- 2026-07-20  shadow-replay  task=2 commit=c5c360612009b492441dd2d1694a48b721d60d14 kind=feature  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-gemini cost_target=$0.1905 judge_cost=$0.0244  truncated=0
- 2026-07-20  shadow-replay  task=4 commit=9f31cda72d103a598b427fa8eacb353ae2b71d94 kind=docs-edit  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-gemini cost_target=$0.0246 judge_cost=$0.0044  truncated=0
- 2026-07-20  shadow-replay  task=5 commit=8fa8d65146b69c11177424f2c8c4e44b1365c9e2 kind=feature  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-gemini cost_target=$0.5770 judge_cost=$0.0339  truncated=0
- 2026-07-20  shadow-replay  task=7 commit=d91ec9bf83cc009c05f0ec46d509274849cff344 kind=config  source=git-lead target=claude-opus-4-8  verdict=worse  judge=judge-gemini cost_target=$0.0959 judge_cost=$0.0077  truncated=0
- 2026-07-20  shadow-replay  task=11 commit=e9f7f270d41a2373e1e973fa87c267c64cfcad6f kind=bugfix  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-gemini cost_target=$0.4745 judge_cost=$0.0244  truncated=0
- 2026-07-20  shadow-replay  task=12 commit=478c3959bd3453247cd8716ab8e5b178e5563ab0 kind=bugfix  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-gemini cost_target=$0.6639 judge_cost=$0.0323  truncated=0
- 2026-07-20  shadow-replay  task=15 commit=f1f4f18e129f569cab421c062a9f52dd38e2c93d kind=mechanism-fix  source=git-lead target=claude-opus-4-8  verdict=worse  judge=judge-gemini cost_target=$0.6035 judge_cost=$0.0323  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=claude-opus-4-8  n=8  equivalent=5/8  judge=judge-gemini  cost_target_total=$2.8191 judge_cost_total=$0.2023  errors=0 truncated=0

КАВЕРАТ СЕРИИ 2026-07-20 (Lead, chief-judge, при приёмке t-221).
(1) ДВЕ АРТЕФАКТНЫЕ СЕКЦИИ выше невалидны как сигнал качества: секция
03:41 (n=8, judge=judge-groq) — класс F-39, дефолт max_tokens=8192
резал «файлы целиком» (truncated=6), плюс 2 error = перелив судьи;
секция n=6 errors=6 (judge-groq, 32000) — НОВЫЙ класс: judge-groq
(free tier) держит TPM 8000 НА ЗАПРОС, суд-промпт с длинным ответом
цели не помещается; рост потолка цели УХУДШАЕТ судимость. Вывод
класса: judge-groq непригоден для длинных пар (кандидат правила в
судейский протокол). Оба дефекта — спека диспетчера (Lead), не
исполнителя.
(2) ВАЛИДНАЯ КАРТИНА Sonnet-цели 2026-07-20: чистые пары секции 03:41
(task=4 equivalent, task=7 worse) + перепрогон judge-gemini (eq:
5,11,12,15; worse: 1,2) = 5/8 equivalent — воспроизводит волну-2
07-18 (тоже 5/8). Кросс-дневная согласованность судьи по тем же
задачам 5/6 (флип только task=2 eq-&gt;worse; объясним вариативностью
генерации цели между прогонами). Устойчиво worse у ОБЕИХ целей —
task=1 и task=7 (класс недоопределённых промптов корпуса, каверат
07-18).
(3) Итог сравнения целей: Sonnet 5/8 = Opus 5/8 (расхождение
составом: Opus прошёл task=2, провалил task=15 — у Sonnet наоборот).
Прирост способности Opus на корпусе принятых работ НЕ измерен;
инструмент имеет потолок по построению (эталон = принятая работа,
лучших вердиктов нет) — дискриминация верха ушла в эскалационный
корпус (gateway/escalation_corpus.jsonl, прогоны ниже).
(4) Свежий source-прогон regression-набора: 9/15 ok; 6 провалов —
из них минимум 3 (ConnectionRefused хвоста) вызваны РЕСТАРТОМ прокси
Lead'ом при живом прогоне (дефект координатора: рестарт без сверки
активных прогонов; правило себе — перед рестартом проверять
процессы), 1 ConnectionReset смежен, 2 Timeout — под нагрузкой.
Следствие: shadow_eval по свежим source-строкам имеет n~9, не 15.
(5) Хвосты в очередь (батч мелочей): (а) дубль метки source_task=
t-027 в regression_set_coding.jsonl; (б) shadow_eval.calibrate()
отбрасывает judge_cost (класс judge_cost=unknown, чинённый в
record_evidence, тут не покрыт).
- 2026-07-20  category=coding  source=lead-sonnet target=claude-opus-4-8  n=10  sim=0.12  judge=judge-sonnet pass_rate=0.90 judge_cost=$0.0996  cost_source=$0.0996 cost_target=$0.1003  errors=0 truncated=0  -> rejected

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-094 commit=1e2a5eac1f78ca36b7bad1460f7ac18dff3143b9 kind=bugfix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-sonnet cost_target=$0.3724 judge_cost=$0.0778  truncated=1
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.3724 judge_cost_total=$0.0778  errors=0 truncated=1

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-097 commit=0ef0aabca6d57ca19e8158fa47b2b2408820cb8a kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-sonnet cost_target=$0.3886 judge_cost=$0.0251  truncated=1
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.3886 judge_cost_total=$0.0251  errors=0 truncated=1

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-201 commit=1a11b80c2f4ade166ffe97a63f7660da7a34a6aa kind=feature  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-sonnet cost_target=$0.0943 judge_cost=$0.1349  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=1/1  judge=judge-sonnet  cost_target_total=$0.0943 judge_cost_total=$0.1349  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-132 commit=761d4f605e2a94ef495eb3b27d6a54190683e473 kind=feature  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-sonnet cost_target=$0.5563 judge_cost=$0.2600  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=1/1  judge=judge-sonnet  cost_target_total=$0.5563 judge_cost_total=$0.2600  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-094 commit=1e2a5eac1f78ca36b7bad1460f7ac18dff3143b9 kind=bugfix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-sonnet cost_target=$unknown judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.0000 judge_cost_total=$0.0000  errors=1 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-094 commit=1e2a5eac1f78ca36b7bad1460f7ac18dff3143b9 kind=bugfix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-sonnet cost_target=$unknown judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.0000 judge_cost_total=$0.0000  errors=1 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-097 commit=0ef0aabca6d57ca19e8158fa47b2b2408820cb8a kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-sonnet cost_target=$unknown judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.0000 judge_cost_total=$0.0000  errors=1 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-097 commit=0ef0aabca6d57ca19e8158fa47b2b2408820cb8a kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=error  judge=judge-sonnet cost_target=$unknown judge_cost=$unknown  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.0000 judge_cost_total=$0.0000  errors=1 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=claude-opus-4-8, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-094 commit=1e2a5eac1f78ca36b7bad1460f7ac18dff3143b9 kind=bugfix  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-sonnet cost_target=$0.8634 judge_cost=$0.3142  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=claude-opus-4-8  n=1  equivalent=1/1  judge=judge-sonnet  cost_target_total=$0.8634 judge_cost_total=$0.3142  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=claude-opus-4-8, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-097 commit=0ef0aabca6d57ca19e8158fa47b2b2408820cb8a kind=mechanism-fix  source=git-lead target=claude-opus-4-8  verdict=worse  judge=judge-sonnet cost_target=$1.2240 judge_cost=$0.3079  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=claude-opus-4-8  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$1.2240 judge_cost_total=$0.3079  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=claude-opus-4-8, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-201 commit=1a11b80c2f4ade166ffe97a63f7660da7a34a6aa kind=feature  source=git-lead target=claude-opus-4-8  verdict=equivalent  judge=judge-sonnet cost_target=$0.1481 judge_cost=$0.1927  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=claude-opus-4-8  n=1  equivalent=1/1  judge=judge-sonnet  cost_target_total=$0.1481 judge_cost_total=$0.1927  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=claude-opus-4-8, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-132 commit=761d4f605e2a94ef495eb3b27d6a54190683e473 kind=feature  source=git-lead target=claude-opus-4-8  verdict=worse  judge=judge-sonnet cost_target=$1.0303 judge_cost=$0.1902  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=claude-opus-4-8  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$1.0303 judge_cost_total=$0.1902  errors=0 truncated=0

КАВЕРАТ СЕРИИ-2 2026-07-20 (Lead, chief-judge, при приёмке t-224).
Судья серии: judge-sonnet (claude-sonnet-5, drop_params), калибровка
13/13 — лучший результат среди судей; предшествовавшие 2 краха
калибровки — класс «Sonnet 5 отвергает temperature=0», закрыт
drop_params на алиасе.
(1) ЭСКАЛАЦИОННЫЙ КОРПУС (gateway/escalation_corpus.jsonl, 4 задачи
с провальной первой попыткой в истории; вопрос — первый выстрел при
ПОЛНОЙ спеке). АРТЕФАКТНЫЕ строки: t-094/t-097 target=lead-sonnet с
truncated=1 (кап 32000 мал для «файлы целиком», класс F-39) и 4
error-пары 64K — это НЕ таймауты: Guard dайли-бюджет lead-sonnet
(default $5.00, budgets.yaml) исчерпан $5.51 — enforcement-слой
сработал по проекту, отказ $0. Следствие: у t-094/t-097 НЕТ валидного
Sonnet-вердикта (недоизмерено, добор после сброса/поднятия бюджета —
решение оператора).
(2) ВАЛИДНАЯ МАТРИЦА: t-201 Sonnet eq $0.09 / Opus eq $0.15; t-132
Sonnet eq $0.56 / Opus WORSE $1.03; t-094 Opus eq $0.86; t-097 Opus
worse $1.22. Прямое сравнение (обе судимы): ничья + победа Sonnet.
Превосходство Opus НЕ обнаружено и на корпусе с headroom.
(3) СОВЕЩАТЕЛЬНОСТЬ: worse-вердикты judge-sonnet по opus-целям —
советные до кросс-аудита judge-gemini (калибровка №4): self-judging
риск (судья = модель sonnet-цели), пары «дифф vs файлы целиком» вне
калибровочного набора.
(4) Также подтверждено «первый выстрел при полной спеке»: t-201 и
t-132 (исторически provalившие первую попытку у builder=Sonnet)
пройдены Sonnet'ом с первого раза — граница ярусов проходила по
качеству спеки, не по способности модели (согласуется с журнальной
эмпирикой: все эскалации окна закрыты тем же ярусом со 2-й попытки).
(5) Дефект печати: cost_target_total/judge_cost_total в строках
shadow_eval при n>1 — СРЕДНЕЕ, не сумма (реальная стоимость шага
coding = $2.00, не $0.20; сверено requests.db). Хвост в батч мелочей
вместе с calibrate()-дропом judge_cost. Реальная стоимость серии-2
$8.22; суммарно обе серии ~ $14.5.
- 2026-07-20  category=coding  source=lead target=lead-sonnet  n=14  sim=0.13  judge=judge-sonnet pass_rate=0.57 judge_cost=$0.0620  cost_source=$0.2690 cost_target=$0.0792  errors=0 truncated=6  -> rejected

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-094 commit=1e2a5eac1f78ca36b7bad1460f7ac18dff3143b9 kind=bugfix  source=git-lead target=lead-sonnet  verdict=equivalent  judge=judge-sonnet cost_target=$0.6141 judge_cost=$0.2680  truncated=0
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=1/1  judge=judge-sonnet  cost_target_total=$0.6141 judge_cost_total=$0.2680  errors=0 truncated=0

### SHADOW-REPLAY D-0080 п.3 (2026-07-20, target=lead-sonnet, ground truth = git-дифф Lead)

- 2026-07-20  shadow-replay  task=t-097 commit=0ef0aabca6d57ca19e8158fa47b2b2408820cb8a kind=mechanism-fix  source=git-lead target=lead-sonnet  verdict=worse  judge=judge-sonnet cost_target=$0.7086 judge_cost=$0.1771  truncated=1
- 2026-07-20  shadow-replay SUMMARY  source=git-lead target=lead-sonnet  n=1  equivalent=0/1  judge=judge-sonnet  cost_target_total=$0.7086 judge_cost_total=$0.1771  errors=0 truncated=1
