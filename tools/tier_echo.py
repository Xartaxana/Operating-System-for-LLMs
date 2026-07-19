"""tier_echo.py -- SubagentStop-хук Claude Code, печатающий координатору
ФАКТИЧЕСКУЮ модель(и) завершившегося субагента, измеренную из его
собственного jsonl-транскрипта -- ответ на инцидент прогона №15
(сессия запросила субагента модели fable, харнесс исполнил его opus'ом,
сессия не заметила и записала в журнал ложный ярус). Класс: требование
яруса без кодовой сверки (D-0063: "код гарантирует ВСТРЕЧУ с замером,
суждение о расхождении остаётся за сессией"). Этот хук не блокирует
ничего и не спорит с сессией -- он просто кладёт измеренный факт перед
ней; сверка ожидаемого с фактическим -- дело сессии/координатора.

КОНТРАКТ SubagentStop payload -- источник dod_gate.py (этот же кит),
эмпирика ТАМ (grep -a установленного бинарника claude.exe, схема XWb),
процитировано дословно из его докстринга: "Payload (схема XWb): базовые
поля (session_id, transcript_path, cwd, prompt_id?) + hook_event_name=
"SubagentStop", stop_hook_active: bool, agent_id, agent_transcript_path,
agent_type, last_assistant_message?, background_tasks?." --
agent_transcript_path -- ОБЯЗАТЕЛЬНОЕ поле именно СОБЫТИЯ SubagentStop
(main_gate.py докстринг подтверждает то же самое отдельной цитатой:
"agent_id/agent_transcript_path/agent_type как ОБЯЗАТЕЛЬНЫЕ поля
СОБЫТИЯ" в схеме XWb) -- значит путь транскрипта завершившегося
субагента детерминированно строится напрямую из payload["agent_transcript_path"],
угадывать по mtime/глобам не требуется и не делается.

ВАЖНАЯ ЭМПИРИЧЕСКАЯ ОГОВОРКА (по цитате выше): подтверждённая схема
XWb НЕ содержит ни поля "model"/"model_id" (запрошенная модель), ни
поля "description" (лейбл диспатча "haiku: ..." / "opus: ..." из
CLAUDE.md правила 7). Оба -- поля ВХОДНОГО tool_input Task/Agent-вызова
(PreToolUse), не подтверждённые как часть SubagentStop-события. Спека
этой задачи, тем не менее, прямо просит: "если payload детерминированно
несёт... ярusный префикс лейбла диспатча (...) в description" --
трактовка: ЕСЛИ payload (вопреки задокументированной схеме, харнесс мог
измениться или нести доп.поля, которых grep не поймал) несёт
"description" в конвенции CLAUDE.md ("<слово>: остальное"), сравнить
его с измеренным; если поля нет -- пропустить MISMATCH-ветку целиком
(measured-часть без флага). На РЕАЛЬНОМ, эмпирически подтверждённом
payload'е эта ветка практически никогда не сработает (поля нет) --
код тем не менее её поддерживает, т.к. спека прямо называет этот
источник, и DoD-тесты покрывают её синтетическими payload'ами.
"Запрошенная модель" отдельным полем НЕ реализована: имя такого поля
нигде не названо ни спекой, ни подтверждённой схемой -- изобретать имя
поля значило бы решать за координатора несуществующим фактом; см.
отчёт builder'а за явную фиксацию этого выбора.

КАНАЛ ВЫВОДА -- тот же, что использует tools/dod_gate.py (спека прямо
просила "тот же канал"): dod_gate.py пишет ЛЮБОЕ своё сообщение (и
BLOCK_MESSAGE при exit 2, и SAFETY_SKIP_MESSAGE при exit 0) ИСКЛЮЧИТЕЛЬНО
через sys.stderr.write(...) -- НЕ через JSON hookSpecificOutput/
additionalContext (та JSON-конвенция, по эмпирике tools/hygiene_gate.py,
существует в харнессе, но НИ ОДИН файл этого кита её не использует для
SubagentStop/Stop; dod_gate.py и main_gate.py оба говорят "exit 2 + текст
в stderr" явно). tier_echo.py следует тому же протоколу: сообщение --
одной строкой в stderr, exit-код ВСЕГДА 0 (эта задача никогда не
блокирует, в отличие от dod_gate.py). Живой смок доставки stderr-текста
координатору при exit-коде 0 НЕ делался (тот же метод/то же ограничение,
что у dod_gate.py/hygiene_gate.py -- потребовал бы Task/Agent-диспатч,
вне роли builder, D-0037); финальная сверка на реальном харнессе -- за
Lead (см. отчёт).

Логика main():
 1. Байтовое чтение stdin (тот же паттерн, что dod_gate.py) -> JSON.
    Сбой парсинга (или payload не dict) -> exit 0 молча.
 2. agent_transcript_path = payload.get("agent_transcript_path") --
    должен быть непустой строкой; иначе (поля нет, пусто, не строка)
    -> exit 0 молча (спека явно запрещает угадывать другим методом).
 3. Прочитать jsonl построчно (байт-безопасно, errors="replace" --
    держит и невалидные UTF-8 БАЙТЫ В САМОМ ФАЙЛЕ, не только stdin);
    файла нет / не открылся -> exit 0 молча. Битые строки JSON --
    пропускаются, не роняют разбор остальных. Для каждой строки с
    type=="assistant" и валидной строкой message.model, НЕ входящей в
    SKIP_MODELS ("<synthetic>" -- харнесс-внутренние stop-sequence-
    строки, tools/usage_report.py:317/401, тот же фильтр) -- счёт хода
    этой модели (порядок первого появления модели в транскрипте --
    порядок вывода). Модель не-строка/пусто/synthetic -- ход не
    считается (но не роняет разбор). ЧЕСТНАЯ СЕМАНТИКА счёта: "=N" --
    число JSONL-строк assistant-типа в транскрипте, а НЕ дедуплицированных
    по requestId API-ходов, как считает usage_report.py -- для эха
    координатору достаточно множества встретившихся моделей и грубого
    счёта строк, дедупликация стоимости здесь не нужна.
 4. Ни одной посчитанной модели (пустой/весь-без-assistant транскрипт)
    -> exit 0 молча -- отчитываться не о чем.
 5. Формирует строку "TIER ECHO (measured): <model>=<turns>[, ...]";
    если payload несёт "description" в конвенции CLAUDE.md ("<слово>:
    ...", слово -- ровно одно из haiku/sonnet/opus/fable) И ни одна
    измеренная model-строка не содержит это слово подстрокой
    (регистронезависимо) -- дописывает " MISMATCH vs declared '<слово>'".
    Строка идёт через ASCII-санитайзер (см. _ascii_sanitize) -- та же
    cp1251-консольная защита, что tools/session_context.py, локальная
    копия (не импорт) по тому же паттерну дублирования, что уже
    применяет dod_gate.py (_extract_agent_id_from_payload) -- каждый
    hook-скрипт этого кита самодостаточен, без межфайловых импортов.
 6. Печатает строку в stderr, exit 0. Любое непредвиденное исключение
    где угодно в main() -- перехватывается ОДНОЙ границей и превращается
    в тихий exit 0 (fail-open, тот же принцип, что во всех хуках кита).
"""

import json
import re
import sys
from pathlib import Path

KNOWN_TIER_WORDS = ("haiku", "sonnet", "opus", "fable")

# Зеркалит tools/usage_report.py:317 -- харнесс-внутренние
# stop-sequence-строки транскрипта несут model=="<synthetic>" (docstring
# usage_report.py:90-92: 6 таких assistant-строк наблюдались эмпирикой
# на этой машине, все с этим значением) -- не реальный ход субагента,
# для эха бессмысленны и искажали бы счёт/список моделей. Тот же
# фильтр, что usage_report.py:401 (`if model in SKIP_MODELS: continue`).
SKIP_MODELS = {"<synthetic>"}


def _ascii_sanitize(s: str, max_len: int = 80) -> str:
    """Локальная копия tools/session_context.py._ascii_sanitize (тот же
    принцип: cp1251-консоль, любое внешне-источниковое значение --
    control-chars вырезаны, non-ASCII заменены, длина ограничена).
    Копия, не импорт -- см. докстринг модуля."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:max_len]


def _extract_agent_transcript_path(payload: dict):
    """agent_transcript_path -- поле СОБЫТИЯ SubagentStop (схема XWb,
    см. докстринг модуля за цитату). Возвращает None, если поля нет,
    оно пустое или не строка -- вызывающий код тогда молча выходит,
    НЕ пытаясь угадать путь другим способом (спека явно запрещает)."""
    value = payload.get("agent_transcript_path")
    return value if isinstance(value, str) and value else None


def _extract_declared_tier(payload: dict):
    """Ищет ярусный префикс лейбла диспатча в payload["description"]
    (конвенция CLAUDE.md правила 7: "haiku: ..." / "sonnet: ..." /
    "opus: ..." / "fable: ..."). Возвращает слово в нижнем регистре,
    только если префикс ДО первого двоеточия РОВНО совпадает с одним
    из KNOWN_TIER_WORDS -- иначе None (нет двоеточия вовсе, префикс
    "opus2" и т.п. -- недетерминируемо, MISMATCH-ветка пропускается
    целиком, см. докстринг модуля/спеку п.4)."""
    description = payload.get("description")
    if not isinstance(description, str) or not description:
        return None
    if ":" not in description:
        return None
    prefix = description.split(":", 1)[0].strip().lower()
    if prefix in KNOWN_TIER_WORDS:
        return prefix
    return None


def iter_transcript_models(path: str):
    """Yields одну строку model на каждый assistant-ход транскрипта, в
    порядке появления в файле. Байт-безопасное построчное чтение
    (errors="replace", тот же принцип, что dod_gate.py/dod_track.py
    для stdin -- ЗДЕСЬ тоже: файл может содержать невалидные UTF-8 байты,
    errors="replace" не роняет чтение, а заменяет их); битые JSON-строки
    -- пропускаются молча, не прерывают разбор остальных строк (DoD:
    "битые jsonl-строки среди валидных -- не падает, считает валидные").
    Формат строки -- по фактическому транскрипту (см. отчёт:
    type=="assistant", message.model) и по
    tools/usage_report.py.iter_assistant_turns -- ТОТ ЖЕ метод чтения
    (top-level "type" + "message"."model") И тот же SKIP_MODELS-фильтр
    синтетических строк (усuление attempt 2, критик-вход): без него
    "<synthetic>" (харнесс-внутренняя stop-sequence-строка,
    tools/usage_report.py:317/401, докстринг usage_report.py:90-92)
    попала бы в счёт как отдельная "модель". Строки с
    message.model отсутствующим/не-строкой/synthetic -- пропускаются
    (не считаются ходом), не роняют разбор.

    Честная семантика счёта (attempt 2, п.3 критика): "=N" в итоговой
    строке -- это счёт JSONL-строк assistant-типа В ЭТОМ транскрипте,
    НЕ дедуплицированных по requestId API-ходов, как делает
    usage_report.py (backfill/dedupe там существует для точного учёта
    стоимости; здесь достаточно множества встретившихся моделей и
    грубого счёта строк для эха координатору)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant":
                continue
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            model = message.get("model")
            if isinstance(model, str) and model and model not in SKIP_MODELS:
                yield model


def count_models(models) -> dict:
    """Считает ходы на модель, СОХРАНЯЯ порядок первого появления
    (обычный dict Python 3.7+ -- порядок вставки), для детерминированного
    вывода build_line()."""
    counts = {}
    for model in models:
        counts[model] = counts.get(model, 0) + 1
    return counts


def build_line(counts: dict, declared_tier) -> str:
    """Собирает итоговую строку из посчитанных моделей (в порядке
    counts, т.е. первого появления) плюс, если применимо,
    MISMATCH-суффикс (спека п.4: MISMATCH, только если declared_tier
    определён И НИ ОДНА measured-модель не содержит его подстрокой,
    регистронезависимо)."""
    parts = [
        f"{_ascii_sanitize(model)}={count}" for model, count in counts.items()
    ]
    line = "TIER ECHO (measured): " + ", ".join(parts)

    if declared_tier:
        matched = any(declared_tier in model.lower() for model in counts)
        if not matched:
            line += f" MISMATCH vs declared '{_ascii_sanitize(declared_tier)}'"

    return line


def main() -> int:
    try:
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            return 0
        if not isinstance(payload, dict):
            return 0

        transcript_path = _extract_agent_transcript_path(payload)
        if not transcript_path:
            return 0

        try:
            models = list(iter_transcript_models(transcript_path))
        except OSError:
            return 0

        counts = count_models(models)
        if not counts:
            return 0

        declared_tier = _extract_declared_tier(payload)
        line = build_line(counts, declared_tier)

        sys.stderr.write(line + "\n")
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
