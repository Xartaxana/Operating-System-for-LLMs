# Спека батча П4 — stdin-дедлайн 12 хуков (драфт designer t-527, принят Lead 08-19)

Статус: принята; диспатч builder — ПОСЛЕ посадки N2 (В6(а): N3 уже
посажен 1e4fb84, остался один живой сиблинг session_context_q503).
Полный драфт с обоснованиями — транскрипт t-527; здесь — операционный
носитель. Свежесть: N3 в драфте помечен «ретрай ожидается» —
ПРОТУХЛО, посажен до приёмки драфта; следствие только для В6 (ждать
одну посадку, не две).

## РЕШЕНИЯ LEAD ПО РАЗВИЛКАМ (08-19)

В1 → (а) fail-open пропуск + одна строка stderr; принятая дыра
enforcement документируется F-62 при посадке (В12): дыра
пред-существует (пустой/битый payload дают тот же пропуск), а
fail-closed на Stop рискует петлёй. В2 → (а) 10.0 с ОБЩИЙ дедлайн;
строка очереди: замерить фактическую доставку payload
инструментовкой. В3 → (а) поток-читатель + join(timeout); В3.1 —
обычный return, эскалация к os._exit(rc) с ручным flush ТОЛЬКО если
K7-эмпирика покажет задержку выхода. В4 → (а) все 12 единообразно.
В5 → (а) session_context на байтовый хелпер + decode("utf-8",
"replace") (снимает носитель класса t-159); перепин
test_f61_halfstate :971-984 двухмирно (K10). В6 → (а) после посадки
N2. В7 → (а) суффикс _p4. В8 → (а) ОДИН builder на все 12 + критик
ОБЯЗАТЕЛЕН (R3: >100 строк, путь enforcement). В9 → (а) кросс-ссылка
search_control_gate :576-586 тем же ходом (K11); (б) gate_log
setdefault-append — строкой очереди в носитель q503 при посадке;
(в) critic_verdict_check :191 — строкой очереди. В10 → (а) батарея
K7 как детектор + (б) probe-лимит времени строкой очереди после N2.
В11 → строка учёта в релизном батче кита при посадке (учёт, не
порт). В12 → F-62 завести при посадке («guard закрывает
интерактивный случай и маскирует неинтерактивный»; принятая дыра В1
документируется там же).

## Канонический хелпер (пин спеки; дословная транскрипция в каждый
из 12 файлов между маркерами; K2 — машинная идентичность регионов)

```python
# --- BEGIN stdin-deadline helper (П4; ЛОКАЛЬНАЯ копия, общий модуль запрещён) ---
_STDIN_DEADLINE_DEFAULT = 10.0
_STDIN_DEADLINE_MAX = 600.0
_STDIN_DEADLINE_ENV = "OSLLM_STDIN_TIMEOUT"


def _stdin_deadline_seconds():
    """Секунды дедлайна: env-переопределение, иначе дефолт. Невалидное,
    нечисловое, <=0 и > _STDIN_DEADLINE_MAX -> дефолт; режима
    "0 = ждать вечно" НЕТ намеренно (он воскрешает саму дыру)."""
    try:
        value = float(os.environ.get(_STDIN_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDIN_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDIN_DEADLINE_MAX):
        return _STDIN_DEADLINE_DEFAULT
    return value


def _read_stdin_bytes_deadline():
    """(bytes, timed_out). Читает stdin до EOF, но не дольше дедлайна.
    Форма кроссплатформенная: select/poll на Windows не работает с
    пайпами, поэтому читает поток-демон, а дедлайн держит join(timeout).
    TTY -> b"" без чтения (прежний guard трёх файлов, теперь у всех).
    Любая ошибка чтения -> b"" (fail-open, как везде в этих хуках)."""
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return b"", False
    try:
        if stdin.isatty():
            return b"", False
    except Exception:
        pass
    stream = getattr(stdin, "buffer", stdin)
    box = {}

    def _reader():
        try:
            box["data"] = stream.read()
        except Exception:
            box["data"] = b""

    thread = threading.Thread(target=_reader, name="stdin-deadline", daemon=True)
    thread.start()
    thread.join(_stdin_deadline_seconds())
    if thread.is_alive():
        return b"", True
    data = box.get("data") or b""
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8", "replace")
    return data, False


_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"
# --- END stdin-deadline helper ---
```

Call-site: `raw_bytes, timed_out = _read_stdin_bytes_deadline()`;
`if timed_out: sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n"); return 0`
(session_context: return None из read_stdin_payload). Дословно
идентичен только регион маркеров; call-site — минимальная правка с
СОХРАНЕНИЕМ существующих ранних return'ов.

## Ключи K1-K13 (из драфта, обязательны)

K1 хелпер ровно раз в каждом из 12, перед main()/(_hook_main),
между маркерами. K2 машинная идентичность 12 регионов против
константы тест-модуля + негативный контроль (искажение в сиблинге,
откат байт-копией с хешем). K3 хелпер — единственная точка чтения
stdin (тест-греп с контролем). K4 rc/каналы на не-таймаутных путях
не меняются: существующие наборы 12 хуков зелены без правок, кроме
K10. K5 на таймауте: rc как у пустого входа (0), stdout ПУСТ,
stderr — одна строка с префиксом имени файла. K6
OSLLM_STDIN_TIMEOUT: дефолт 10.0; ветки невалидного (пусто/abc/0/
-1/1e9/600.1) → дефолт, 600 проходит; тесты на каждую. K7 на
границе (~0.8 дедлайна с закрытием → штатный путь) и за (writer не
закрыт → завершение в дедлайн+запас, K5). K8 TTY-guard у всех 12
(тест по образцу test_session_context :812-821). K9 фейки stdin без
isatty работают (test_critic_snapshot :74-77 зелен без правок).
K10 session_context на байты; перепин test_f61_halfstate :971-984
двухмирно. K11 кросс-ссылка search_control_gate снята. K12
диагностика НЕ печатается ни на одном не-таймаутном пути (контракт
test_hygiene_gate :1369 stderr==""). K13 перечисление 12 файлов:
try-граница вызова + сохранённый ранний return у каждого.

## Края (несущие; полный список — транскрипт t-527 §4)

Пустой-с-EOF: существующее поведение ДОСЛОВНО у каждого (у
search_control_gate пустой вход зовёт _process и пишет образец
схемы — на ТАЙМАУТЕ _process НЕ зовётся, единственное named
расхождение). TTY у 9 — смена поведения (часть фикса, K8).
Частичный JSON + тишина → отбрасывание, K5. Медленный большой
payload → усечение (цена принята, В2-очередь). Темпоральные: env
не существует до батча; сиблинги _p4 — три мира P4_TARGET.
Позиционный инвариант (K13): _reconfigure_utf8 ДО чтения; чтение
внутри существующих fail-open границ; тотальный try у
dispatch_gate/dod_gate/main_gate НЕ добавляется (решение Р3а F-61);
payload-зависимая логика недостижима на таймаутном пути.

## Поправка Lead при диспатче (08-19, чеклист п.5 — свежесть)

Греп `sys.stdin|stdin.buffer` по tools/*.py перед диспатчем: 14
не-тестовых читателей, не 12+critic_verdict_check. Драфт t-527
пропустил `tools/tier_echo.py` (`:247` — блокирующее
`sys.stdin.buffer.read()` payload'а, тот же класс дыры). Решение
Lead: батч расширен до **13 файлов** (В4 «единообразно»; молча
оставленный известный сиблинг = нарушение R9); все ключи K1-K13
применяются к tier_echo той же формой (в K2/K13 счёт «12» читать
«13»); owns += tools/tier_echo_p4.py. Перечисление 13 (греп-факт):
session_context, hygiene_gate, journal_echo, dispatch_gate,
owns_gate, dod_track, dod_gate, main_gate, negative_lint,
claim_control_gate, search_control_gate, critic_snapshot, tier_echo.

## DoD (команды из драфта §7 — дословно; красная половина ~1.5 мин
по конструкции — назвать; негативный контроль K2 с хеш-откатом;
суженный прогон — 22 тест-файла списком из драфта; BATCH CANON —
координатор). owns: 12 сиблингов *_p4 + test_p4_stdin_deadline.py +
test_f61_halfstate.py (перепин K10). Не-цели: живые 12 (посадка
Lead одним механизменным коммитом); settings.json; общий модуль;
decide()/gate_log; critic_verdict_check; probe/exam_runner; сиблинг
session_context_q503 (чужой до посадки N2); docs/PROCESS/CLAUDE.md;
кит-твины. Handoff: проба живости всех событий + probe; строки
посадки: F-62, очереди В9б/в/В10б/В2, учёт кита В11.
