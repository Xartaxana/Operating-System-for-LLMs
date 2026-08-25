# Спека: сужение предиката pyc (гигиена п.4) — драфт t-600, принят Lead 15:40

## ПОПРАВКА LEAD 16:35 (развилка билдера t-605 — противоречие спеки доказано)

Билдер эмпирически показал: классификация без привязки к уверенности
извлечения ломает 16+ живых пинов (обёрточная группа E11, прозовые
упоминания, switch-off), а «четыре теста» F5(A) — недосчёт дизайнера.
РЕШЕНИЕ — вариант (а) с уточнением:
- `pyc_payload` вычисляется ТОЛЬКО при `pyc_certain == True`;
  при `pyc_certain == False` значение «U» (unclassified).
- Поведение warn-ветки: P → тишина; M → старый `MSG_PYTHON_DASH_C`;
  O → `MSG_PYTHON_DASH_C_OPAQUE`; **U → старое безусловное поведение
  со старым текстом `MSG_PYTHON_DASH_C`** (обёртки/проза/эмбеддинг не
  ослабляются и не переименовываются).
- Определение P сужено: «доказанная чистота НАДЁЖНО ИЗВЛЕЧЁННОГО
  payload'а честной самостоятельной формы python -c/heredoc».
- Честный список правленых существующих тестов = четвёрка F5(A) +
  пять certain-чистых пинов, найденных билдером
  (test_vg5_python_open_read_mode..., test_adversarial_nested_quotes...,
  test_v5_..._journal_path_as_prose... ×2, test_p6_switch_off_stays_warn...)
  — КАЖДЫЙ перечисляется в отчёте с формой правки (фикстура →
  мутирующий payload ЛИБО ожидание → тишина, по смыслу пина).
  Обёрточные (E11), прозовые (:2542-2583) и deny-тела — НЕ трогаются,
  их зелень без правки — часть акцептанса.
- E1 (пустой payload, certain-форма) → O, как в спеке; A1-A10 в силе
  с поправкой «тишина = certain и P». F5(A)-недосчёт — spec-defect
  дизайнера, записан (R11(n)).

- F1(A): НОВЫЙ ключ `pyc_payload` в `_collect_v5_signals`; `pyc`/`pyc_certain` НЕ тронуты (инвариант I1).
- F2: классификация — `ast.parse` payload'а, обход дерева; любой сбой парсера → класс O. Токенный список — только как дополнительный быстрый фильтр непрозрачности ДО парсинга, не вместо AST.
- F3(A): измеритель permission_audit остаётся на ключе `pyc`; обязательная строка в докстринге `classify_hygiene` о расхождении «счёт класса ≠ счёт варна»; правку текста чека 25 исполняет Lead отдельным ходом (НЕ этот диспатч).
- F4(A): асимметрия deny/warn на чистом payload ПРИНЯТА, пинится тестом (чистый payload при PYC_DENY_ENABLED=True → deny).
- F5(A): фикстуры четырёх существующих тестов с `print(1)` переводятся на мутирующий payload; КАЖДАЯ правка живого теста перечисляется в отчёте. F5b: текст `MSG_PYTHON_DASH_C` НЕ меняется.
- F6: два вызова разных классов → ОДНА строка варна строжайшего класса (M > O > P).
- F7: пустой payload → O.
- F8(A): `.write(`/`.writelines(` на чём угодно → M, КРОМЕ явных `sys.stdout`/`sys.stderr`; `print(..., file=X)` при X не stdout/stderr → M.
- F9: лимит L1 = 20 000 символов; замер времени (100КБ/1МБ) прикладывается ЧИСЛОМ, порогом не гейтится.
- F10: различение «инлайн против именованного скрипта» — в НОРМУ (амендмент п.4, исполняет Lead), в код НЕ входит.
- F11: расширение на python3/py/pwsh НЕ делается (Р16 остаётся).
- F12: кит-твин — порт-очередь релиза (не этот диспатч).

## ПОПРАВКА LEAD 17:2x — фикс-раунд по вердикту критик-гейта (БЛОКЕР)

Вердикт (транскрипт критик-агента t-605): реально пишущий код уходит
в P → тишина (регресс: `Path('x').write_text(...)` молчит, до диффа
был WARN). Решения:

- **Ось B (обязательно, несоответствие F8):** attr берётся из
  `node.func.attr` при `isinstance(node.func, ast.Attribute)`
  НЕЗАВИСИМО от dotted; исключение sys.stdout/sys.stderr — только по
  разрешимой base_dotted, неразрешимая база → правила применяются
  (консервативно). Дополнительно: `attr == "open"` с литеральным
  режимом w/a/x/+ → M на ЛЮБОЙ базе (закрывает Path().open('w'),
  io.open, pathlib.Path.open).
- **Ось A:** алиас-карта импортов строится обходом
  ast.Import/ast.ImportFrom (включая asname; ImportFrom мапит ИМЯ на
  module.name); корни вызовов резолвятся через карту ДО сопоставления
  с M/O-списками. Плюс: ast.Assign/AnnAssign/NamedExpr, чьё значение —
  Name/Attribute, ссылающееся на `open` или любое M/O-имя
  (`w = open`) → класс O (переприсваивание callable = непрозрачность).
- Тест на КАЖДУЮ из 12 атак-строк вердикта (`test_pycnarrow_alias_*`,
  `test_pycnarrow_chained_receiver_*`), включая худший экземпляр
  (журнальный Path.write_text → M, WARN).
- **Ф1:** исходные фикстуры :1650/:1672 (упоминание пути БЕЗ формы
  записи) возвращаются СОСЕДНИМИ тестами с ожиданием `output is None`
  (P → полная тишина, журнальный класс молчит) и честными
  комментариями; правленые пины остаются отдельно.
- **Ф2:** `_is_python_dash_c_certain` не считается дважды — готовый
  флаг передаётся опциональным параметром (публичная одноаргументная
  сигнатура сохраняется).
- **Ф3:** квадратичность формы «повторённые опенеры без закрывателя»
  предсуществующая — НЕ чинится этим раундом; в перф-тест — строка,
  что число A8 относится к доброкачественной форме; очередь — носитель
  queue8-closure.md.
- Докстринг P остаётся «доказанной чистотой» ТОЛЬКО при посадке всех
  фиксов осей A/B; остаточная граница (глубокий dataflow) уже покрыта
  O-списком (getattr/exec/динамика).

## ТРЕБУЕМОЕ ПОВЕДЕНИЕ (из драфта, нормативно)

Трёхклассовая семантика payload: **M** (мутация ФС) → WARN текстом `MSG_PYTHON_DASH_C` ДОСЛОВНО КАК СЕЙЧАС; **P** (доказанная чистота: ни мутаций, ни непрозрачности) → ТИШИНА; **O** (непрозрачность/сбой парсинга/пустой или неизвлечённый payload/сверх лимита) → WARN новой константой `MSG_PYTHON_DASH_C_OPAQUE`:
«payload python -c/heredoc непрозрачен (exec/eval/subprocess/динамика, гигиена п.4): гейт не может доказать отсутствие записи — вынеси код в именованный файл (python <path>, в т.ч. scratchpad)».

Извлечение payload — по СЫРОЙ команде, ДО масок (`_mask_heredoc_bodies` затирает тело): аргумент -c (строковый литерал либо голый токен) и тело `python - <<DELIM…DELIM`.

Список МУТАЦИИ (закрытый): open с литеральным режимом w/a/x/+; open с НЕлитеральным режимом → O; open(path) без режима → вклад P; Path .write_text/.write_bytes/.unlink/.rename/.replace/.mkdir/.touch/.rmdir; os.remove/.unlink/.rename/.replace/.rmdir/.mkdir/.makedirs/.truncate/.chmod; shutil.*; json.dump(, pickle.dump(, csv.writer(, .to_csv(, .to_excel(; .write(/.writelines( кроме sys.stdout/sys.stderr; print(..., file=X) при X не stdout/stderr.
Список НЕПРОЗРАЧНОСТИ: exec, eval, compile, __import__, importlib.*, subprocess.*, os.system, os.popen, os.exec*, os.spawn*, ctypes.*, marshal.*, getattr(/setattr(/globals(/locals(/vars(/builtins, socket.*, urllib.*, requests.*, multiprocessing.*, pty.*, fileinput.input(...inplace...).

Точка встраивания — ЕДИНСТВЕННАЯ правка решателя, сборка warn_reasons (hygiene_gate.py ~:1702-1703): `if pyc_hit and not pyc_deny and payload_class != "P": warn_reasons.append(<текст по классу>)`.

## ИНВАРИАНТЫ (пины)

- I1: имя и смысл ключа `pyc` неизменны — permission_audit (:509-578) и test_permission_audit (:520-545) читают по именам, baseline чека 25 «python -c x7»; всё, что давало pyc=True, даёт и после.
- I2: deny-путь не тронут НИ СТРОКОЙ (`pyc_certain` :1530-1558, `_mask_heredoc_bodies` :1463-1527, `PYC_DENY_ENABLED`); всё, что блокировалось, блокируется (список deny-тестов в A4 ниже).
- I3: порядок deny_reasons журнал→cd→2>&1→pyc и `permissionDecisionReason=deny_reasons[0]` не меняются; классификатор недостижим для команд с deny-вкладом класса (в); порядок warn cd→redirect→pyc сохраняется.
- I4: V4-путь (`_decide_v4`/`_collect_warn_classes` :1003-1020) байт-в-байт.
- I5: тексты — ВНУТРИ существующих префиксов «Командная гигиена: »/«Командная гигиена (WARN, не блокирует): »; запись HYGIENE в warn_layers.json НЕ меняется; НОВЫЙ префикс вводить ЗАПРЕЩЕНО (реестр вне owns).

## АКЦЕПТАНС A1-A10 (дословно из драфта)

A1 `python -c "print(1+1)"` → (0, None); то же для чтения json. A2 `open('x.txt','w')` → WARN MSG_PYTHON_DASH_C. A3 subprocess → WARN OPAQUE, без M-текста. A4 при monkeypatch PYC_DENY_ENABLED=True все существующие deny-тесты зелены БЕЗ правки тел (test_p6_dash_c_deny_basic, test_p6_heredoc_opener_deny, test_p6_real_python_heredoc_own_body_mentioning_dash_c_still_denies, test_p6_adversarial_emoji_non_ascii_payload_still_denies, test_p6_adversarial_bare_python_dash_c_no_payload_denies, test_p6_wrapper_control_real_dash_c_still_denies, test_p6_positional_journal_deny_reason_unchanged_by_pyc_addition, test_p6_positional_cd_root_deny_reason_unchanged_by_pyc_addition, test_p6_positional_redirect_certain_deny_reason_unchanged_by_pyc_addition) + новый тест асимметрии (чистый payload при deny-выключателе → deny). A5 `_collect_v5_signals('python -c "print(1+1)"')["pyc"] is True`; classify_hygiene даёт ["python -c/heredoc"]; тест равенства гейт==измеритель зелён без правки. A6 V5_ENABLED=False → как сегодня для всех трёх классов. A7 батарея без трейсбеков, exit всегда 0. A8 замер 100КБ/1МБ приложен числом (именованным закоммиченным тестом, не инлайн python -c). A9 `python tools/warn_density.py --check` → exit 0 (новых префиксов нет). A10 докстринги называют I1 и I2 явно.

## КРАЯ E1-E15 и БАТАРЕЯ B1-B14 — по драфту t-604... (опечатка: t-600); дословно:

E1 пустой payload (python -c, -c "", пустой heredoc) → O. E2 многострочный/heredoc-тело целиком по сырому. E3 'w' внутри строкового литерала → P. E4 кодировки/эмодзи/BOM → не падать, недекодируемое → O. E5 PYTHON -C: pyc=True сохраняется; классификация регистрозависима (OPEN('x','w') → P, законно: NameError в Python). E6 комментарий → P. E7 два вызова → строжайший класс, одна строка. E8 open(p)→P, open(p,'r')→P, 'w'/'a'/'x'/'r+'→M, mode-переменная→O, **kw→O, mode='w' kwarg→M. E9 не-Python → O. E10 сверх L1 → O без парсинга. E11 обёрточные формы: если payload извлекается — классифицируется, нет → O; тесты wrapper_*_not_covered_known_limitation зелены БЕЗ правки тел. E12 упоминание как данных (git commit -F heredoc) → O → WARN как сегодня. E13 битый вход → тишина как сегодня. E14 конфликт deny×тишина решён: сужение ТОЛЬКО warn-ветки, асимметрия запинена. E15 конфликт ключ-неизменен×измеритель: расхождение объявлено докстрингом.

B1 payload ровно L1 → парсится; B2 L1+1 → O; B3 команда 1МБ → exit 0, время приложено; B4 вложенность 50 → P; B5 вложенность 5000 → O без трейсбека; B6 эмодзи/греческий → P; B7 незакрытая кавычка → O; B8 heredoc без закрывателя → O; B9 два вызова → одна строка M; B10 мутация в строковом литерале → P; B11 __import__('os').remove → O (и M>O при обоих); B12 null-байты в stdin → exit 0; B13 payload из пробелов → O; B14 pyc+journal одновременно, payload чистый → журнальный deny/warn не изменён, pyc-строки нет.

Имена (закрыто дизайнером): ключ `pyc_payload` ("M"|"P"|"O"), функция `_classify_pyc_payload(command) -> str`, константа `MSG_PYTHON_DASH_C_OPAQUE`, тесты `test_pycnarrow_*` отдельной секцией.

## owns: tools/hygiene_gate.py, tools/test_hygiene_gate.py.
## non-goals: кит-твин; CLAUDE.md/POLICY_FULL (Lead); включение PYC_DENY_ENABLED; python3/py/pwsh; прочие сигналы; обёрточная дыра; tools/permission_audit.py (F3(A): докстринг classify_hygiene — ЕДИНСТВЕННОЕ исключение, одна строка, добавить файл в owns при правке); warn_layers.json.

## СУЖЕННЫЙ WITNESS (волна 2 параллельна, R4; канон снимет координатор):
`python -m pytest tools/test_hygiene_gate.py tools/test_permission_audit.py -q` + `python tools/warn_density.py --check` + замер A8 числом + негативный контроль по классам (по одной команде M/P/O с фактическим вердиктом, включая ту, что обязана молчать) + перечисление КАЖДОГО правленого существующего теста.
