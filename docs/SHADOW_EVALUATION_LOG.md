# Shadow Evaluation Log

Evidence for DELEGATION_TABLE.md Update Rule 1 — one line per Shadow
Evaluation run. Relocated VERBATIM from DELEGATION_TABLE.md
2026-07-10 (D-0067, boot diet round 2: the table stays in the boot
path, closed run history does not). NEW runs append HERE; a table
status change cites its evidence line in this file.

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
