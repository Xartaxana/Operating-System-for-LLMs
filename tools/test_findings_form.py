"""Машинный слой D-0100 (Д2): проверяет форму записи «Вопрос
применимости» в docs/FINDINGS.md.

Норма (шапка docs/FINDINGS.md, коммит 258ad6c, 2026-08-09; якорь даты
уточнён решением координатора t-380-продолжение): запись, несущая
секцию **Класс.**, с датой >= 2026-08-09 в ПЕРВОМ ПОЛЕ записи (или
БЕЗ даты в первом поле вовсе -- fail-closed) обязана нести секцию
**Вопрос применимости.** СРАЗУ ПОСЛЕ **Класс.** (между ними -- только
пустые строки/продолжающая проза без своего маркера). Записи с датой
< 2026-08-09 освобождены. Записи без секции **Класс.** -- поле не
требуется.

ЯКОРЬ ДАТЫ (не «где угодно в записи» -- иначе пост-отсечная запись,
цитирующая в прозе старое событие, получила бы ложное освобождение):
первое вхождение YYYY-MM-DD в ПЕРВОМ АБЗАЦЕ записи, начинающемся
жирным маркером, каким бы ни было его имя (**Дата:**, историческая
форма **Наблюдение (дата, источник)**, что угодно). Досыл РОВНО НА
ОДИН шаг (F-53-класс): если у этого первого жирного поля даты нет,
берётся первый абзац записи целиком (жирный он или нет -- вводная
проза без разметки, предшествующая первому жирному полю). Дальше не
расширяется.

Парсер терпим к вариациям НЕпроверяемых полей (Факт/Ремедиация/
Детектор/Статус -- их точная форма не разбирается вовсе, только
проверяемые: Класс, дата первого поля, Вопрос применимости). Маркер
внутри fenced-блока кода или цитаты (`>`) не считается заполнением --
«цитата не утверждение»: перед разбором записи маскируются такие
диапазоны (текст затирается пробелами, переводы строк сохраняются).

Модуль самодостаточен (re/datetime/pathlib/pytest), репозиторных
импортов нет -- совпадает с канонической формой прогона
(`python -m pytest tools/ gateway/ -q`), а также с узким таргетом
`python -m pytest tools/test_findings_form.py -q`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

FINDINGS_PATH = Path(__file__).resolve().parent.parent / "docs" / "FINDINGS.md"

CUTOFF = date(2026, 8, 9)

HEADER_RE = re.compile(r"(?m)^##\s+(F-\d+)\b.*$")
FENCE_RE = re.compile(r"(?ms)^```.*?^```")
QUOTE_LINE_RE = re.compile(r"(?m)^[ \t]*>.*$")

KLASS_RE = re.compile(r"\*\*Класс\.?\*\*")
VOPROS_RE = re.compile(r"\*\*Вопрос применимости\.?\*\*")
# любой жирный маркер-поле в начале абзаца (Факт./Класс./Ремедиация./
# Детектор./Статус./Дата: и т.п., включая неизвестные вариации формы --
# парсер терпим к их точной форме, но должен УЗНАВАТЬ, что абзац
# начинает НОВОЕ поле, а не является продолжающей прозой предыдущего)
FIELD_MARKER_RE = re.compile(r"^\*\*[^*\n]{1,80}?[.:]\*\*")


def _mask(text: str) -> str:
    """Затирает пробелами fenced-код-блоки и строки-цитаты (`>`),
    сохраняя переводы строк -- маркер внутри такого диапазона
    перестаёт совпадать с регэкспом ниже по тексту."""

    def _blank(m: "re.Match[str]") -> str:
        return "".join(ch if ch == "\n" else " " for ch in m.group(0))

    text = FENCE_RE.sub(_blank, text)
    text = QUOTE_LINE_RE.sub(_blank, text)
    # строки, ставшие после маскировки чисто пробельными, -- в пустые,
    # чтобы разбивка на абзацы ниже считала их блочным разделителем
    lines = text.split("\n")
    lines = ["" if line.strip(" \t") == "" else line for line in lines]
    return "\n".join(lines)


def _paragraphs(masked: str) -> list[str]:
    """Абзацы -- блоки текста, разделённые >=1 пустой строкой (после
    маскировки). Пустые абзацы отбрасываются."""
    parts = re.split(r"\n{2,}", masked.strip("\n"))
    return [p for p in parts if p.strip() != ""]


@dataclass
class RecordCheck:
    name: str
    has_klass: bool
    has_date: bool
    date_value: date | None
    subject_to_rule: bool
    vopros_present_anywhere: bool
    vopros_immediately_after_klass: bool

    @property
    def ok(self) -> bool:
        if not self.subject_to_rule:
            return True
        return self.vopros_immediately_after_klass

    @property
    def reason(self) -> str:
        if self.ok:
            return "ok"
        if not self.vopros_present_anywhere:
            return "Вопрос применимости отсутствует вовсе"
        return "Вопрос применимости есть, но не сразу после Класс"


def _first_date_in_text(text: str) -> date | None:
    """Первое вхождение YYYY-MM-DD в тексте (валидное как дата);
    невалидные совпадения (напр. 2026-13-40) пропускаются в пользу
    следующего совпадения, если такое есть."""
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", text):
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
    return None


def _anchor_date(paragraphs: list[str]) -> date | None:
    """Якорь даты записи (решение координатора, t-380 продолжение):
    дата читается из ПЕРВОГО ПОЛЯ записи -- первого абзаца,
    начинающегося жирным маркером, каким бы ни было его имя
    (**Дата:**, **Наблюдение (...)**, что угодно) -- первое вхождение
    YYYY-MM-DD внутри ЭТОГО абзаца, а не где угодно в записи (иначе
    пост-отсечная запись, цитирующая старую дату в прозе тела,
    получила бы ложное освобождение).

    Досыл (F-53-случай): если у первого жирного поля даты нет вовсе
    (историческая запись, где сама дата стоит ДО первого жирного
    маркера, вводным абзацем без разметки) -- якорь расширяется
    РОВНО НА ОДИН шаг: первый абзац записи целиком (жирный он или
    нет). Дальше не расширяется -- пусто на этом шаге тоже = дата
    отсутствует (fail-closed)."""
    if not paragraphs:
        return None
    narrow_idx = None
    for i, p in enumerate(paragraphs):
        if FIELD_MARKER_RE.match(p.lstrip()):
            narrow_idx = i
            break
    if narrow_idx is not None:
        d = _first_date_in_text(paragraphs[narrow_idx])
        if d is not None:
            return d
    # досыл: первый абзац записи целиком (может совпадать с narrow_idx
    # == 0, тогда это no-op; для F-53-класса -- это вводная проза ДО
    # первого жирного поля)
    return _first_date_in_text(paragraphs[0])


def parse_record(name: str, raw_body: str) -> RecordCheck:
    """Разбирает тело ОДНОЙ записи (текст между её заголовком `## F-NN`
    и следующим заголовком/концом файла) и возвращает вердикт формы."""
    body = raw_body.replace("\r\n", "\n").replace("\r", "\n")
    masked = _mask(body)

    klass_match = KLASS_RE.search(masked)
    has_klass = klass_match is not None

    paragraphs = _paragraphs(masked)
    date_value = _anchor_date(paragraphs)
    has_date = date_value is not None

    vopros_present_anywhere = VOPROS_RE.search(masked) is not None

    subject = has_klass and (not has_date or date_value >= CUTOFF)

    vopros_immediately_after = False
    if has_klass:
        klass_idx = None
        for i, p in enumerate(paragraphs):
            if KLASS_RE.match(p.lstrip()):
                klass_idx = i
                break
        if klass_idx is not None:
            # Класс -- секция, а не один абзац: продолжающая прозу
            # (абзац, НЕ начинающийся жирным маркером нового поля)
            # -- всё ещё часть Класса ("между ними -- только пустые
            # строки" читается как "никакое ДРУГОЕ ПОЛЕ не встряло").
            # Первый абзац, начинающийся любым жирным полем-маркером,
            # -- это и есть "следующее поле"; проверяем, что оно --
            # Вопрос применимости.
            for j in range(klass_idx + 1, len(paragraphs)):
                nxt = paragraphs[j].lstrip()
                if VOPROS_RE.match(nxt):
                    vopros_immediately_after = True
                    break
                if FIELD_MARKER_RE.match(nxt):
                    # встряло другое поле раньше Вопроса
                    vopros_immediately_after = False
                    break
                # иначе -- продолжающая проза Класса, идём дальше

    return RecordCheck(
        name=name,
        has_klass=has_klass,
        has_date=has_date,
        date_value=date_value,
        subject_to_rule=subject,
        vopros_present_anywhere=vopros_present_anywhere,
        vopros_immediately_after_klass=vopros_immediately_after,
    )


def extract_records(full_text: str) -> list[tuple[str, str]]:
    """Разбивает документ FINDINGS.md на записи по заголовкам `## F-NN`.
    Текст до первого такого заголовка (преамбула, включая норму
    D-0100 в шапке) в разбор не идёт вовсе -- не запись."""
    text = full_text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(HEADER_RE.finditer(text))
    records = []
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        records.append((name, text[start:end]))
    return records


# ---------------------------------------------------------------------
# T3 -- адверсариальная батарея на парсер (синтетические тексты).
# ---------------------------------------------------------------------


def test_empty_text():
    c = parse_record("F-EMPTY", "")
    assert c.has_klass is False
    assert c.ok is True  # не подпадает вовсе -- пустая запись не Класс


def test_record_without_klass():
    body = """
**Дата:** 2026-08-09.

**Факт.** Что-то случилось, но секции Класс нет вовсе.

**Статус.** Открыта.
"""
    c = parse_record("F-NOKLASS", body)
    assert c.has_klass is False
    assert c.subject_to_rule is False
    assert c.ok is True


def test_vopros_marker_inside_fenced_code_block_does_not_count():
    body = """
**Дата:** 2026-08-09.

**Класс.** Текст класса дефекта.

```
**Вопрос применимости.** это внутри кодового блока, цитата не факт.
```

**Статус.** Открыта.
"""
    c = parse_record("F-FENCE", body)
    assert c.has_klass is True
    assert c.subject_to_rule is True
    # маркер физически присутствует в тексте, но маскирован -- не
    # засчитывается ни как "где-то есть", ни тем более как "сразу после"
    assert c.vopros_present_anywhere is False
    assert c.vopros_immediately_after_klass is False
    assert c.ok is False


def test_vopros_marker_inside_blockquote_does_not_count():
    body = """
**Дата:** 2026-08-09.

**Класс.** Текст класса дефекта.

> **Вопрос применимости.** это цитата, не утверждение записи.

**Статус.** Открыта.
"""
    c = parse_record("F-QUOTE", body)
    assert c.has_klass is True
    assert c.subject_to_rule is True
    assert c.vopros_present_anywhere is False
    assert c.vopros_immediately_after_klass is False
    assert c.ok is False


def test_crlf_text_parses_same_as_lf():
    body_lf = "**Дата:** 2026-08-09.\n\n**Класс.** Текст.\n\n**Вопрос применимости.** Вопрос?\n"
    body_crlf = body_lf.replace("\n", "\r\n")
    c_lf = parse_record("F-LF", body_lf)
    c_crlf = parse_record("F-CRLF", body_crlf)
    assert c_lf.ok is True
    assert c_crlf.ok is True
    assert c_lf.vopros_immediately_after_klass == c_crlf.vopros_immediately_after_klass


def test_marker_case_variation_not_recognized():
    # Класс/Вопрос применимости распознаются в канонической
    # капитализации (как реально пишутся в FINDINGS.md); строчный
    # вариант этих ДВУХ маркеров -- НЕ считается полем, чтобы обычное
    # упоминание слова "класс"/"вопрос" в прозе не ложно
    # засчитывалось структурным маркером. Якорь даты -- отдельная
    # история: он ищет ЛЮБОЙ жирный маркер как "первое поле" (имя поля
    # не имеет значения для якоря по решению координатора), поэтому
    # "**дата:**" здесь всё равно даёт дату, но это не делает запись
    # подпадающей -- Класс не распознан, а без Класса требование не
    # применяется вовсе.
    body = """
**дата:** 2026-08-09.

**класс.** текст класса дефекта строчными буквами.

**вопрос применимости.** вопрос строчными буквами.
"""
    c = parse_record("F-LOWER", body)
    assert c.has_klass is False
    assert c.has_date is True  # якорь -- любой жирный маркер, регистр не важен
    assert c.subject_to_rule is False  # но без Класса требование не действует
    assert c.ok is True


def test_record_without_date_field_falls_under_rule_fail_closed():
    body = """
**Класс.** Текст класса без секции Дата вовсе.

**Статус.** Открыта.
"""
    c = parse_record("F-NODATE", body)
    assert c.has_klass is True
    assert c.has_date is False
    assert c.subject_to_rule is True  # fail-closed
    assert c.ok is False  # Вопрос применимости отсутствует


def test_cutoff_boundary_exact_date_is_subject():
    body = """
**Дата:** 2026-08-09.

**Класс.** Текст класса ровно на дату отсечки.

**Статус.** Открыта.
"""
    c = parse_record("F-BOUNDARY-ON", body)
    assert c.date_value == CUTOFF
    assert c.subject_to_rule is True
    assert c.ok is False  # Вопрос применимости отсутствует -- должен упасть


def test_cutoff_boundary_day_before_is_exempt():
    body = """
**Дата:** 2026-08-08.

**Класс.** Текст класса за день до отсечки.

**Статус.** Открыта.
"""
    c = parse_record("F-BOUNDARY-OFF", body)
    assert c.date_value == date(2026, 8, 8)
    assert c.subject_to_rule is False
    assert c.ok is True  # освобождена -- Вопрос применимости не требуется


def test_historical_nablyudenie_form_before_cutoff_is_exempt():
    # историческая форма "**Наблюдение (дата, источник).**" в первом
    # поле, дата до отсечки -- освобождена (эмпирический класс
    # F-11..F-31: якорь читает дату из ЛЮБОГО имени первого поля).
    body = """
**Наблюдение (2026-07-08, оператор).** Что-то случилось.

**Класс.** Текст класса.
"""
    c = parse_record("F-NABL-BEFORE", body)
    assert c.date_value == date(2026, 7, 8)
    assert c.subject_to_rule is False
    assert c.ok is True


def test_historical_nablyudenie_form_after_cutoff_is_subject():
    # та же форма, но дата ПОСЛЕ отсечки -- подпадает под требование.
    body = """
**Наблюдение (2026-08-10, оператор).** Что-то случилось.

**Класс.** Текст класса.
"""
    c = parse_record("F-NABL-AFTER", body)
    assert c.date_value == date(2026, 8, 10)
    assert c.subject_to_rule is True
    assert c.ok is False  # Вопрос применимости отсутствует


def test_post_cutoff_date_field_not_fooled_by_old_date_in_body_prose():
    # якорь -- ТОЛЬКО первое поле; пост-отсечная запись с корректной
    # **Дата:** после отсечки, но упоминающая старую дату где-то в
    # прозе тела (например, цитируя инцидент), НЕ получает ложного
    # освобождения по этой старой дате -- запись подпадает.
    body = """
**Дата:** 2026-08-09.

**Факт.** Ссылаясь на инцидент 2026-07-08, повторившийся снова.

**Класс.** Текст класса.
"""
    c = parse_record("F-NOFALSEEXEMPT", body)
    assert c.date_value == CUTOFF  # взята дата ПЕРВОГО поля, не 2026-07-08 из прозы
    assert c.subject_to_rule is True
    assert c.ok is False  # Вопрос применимости отсутствует


def test_no_date_anywhere_in_first_field_or_first_paragraph_fail_closed():
    # запись вовсе без даты в первом поле (и первый абзац тоже без
    # даты, т.е. досыл на F-53-случай тоже не находит её) -- fail-closed,
    # даже если где-то ДАЛЬШЕ в записи дата упомянута (якорь не
    # проваливается в более поздние поля).
    body = """
**Факт.** Что-то случилось, без даты в этом поле.

**Класс.** Текст класса.

**Источник.** Событие 2026-07-08 зафиксировано где-то здесь, но не в
первом поле и не в первом абзаце -- якорь его не видит.
"""
    c = parse_record("F-NODATE-DEEP", body)
    assert c.has_date is False
    assert c.subject_to_rule is True
    assert c.ok is False


def test_f53_class_plain_prose_intro_before_first_bold_field_widens_anchor():
    # регресс на F-53: первый абзац записи -- ПРОЗА без жирного
    # маркера, несущая дату; первое ЖИРНОЕ поле идёт следом и своей
    # даты не содержит. Узкий якорь (первое жирное поле) не находит
    # дату -- досыл на первый абзац целиком находит.
    body = """
2026-07-22, деплой Dog (записано их сессией). Их pre-commit перестал
блокировать коммиты.

**Механика.** Технические детали без даты внутри.

**Класс.** Текст класса.
"""
    c = parse_record("F-53-LIKE", body)
    assert c.date_value == date(2026, 7, 22)
    assert c.subject_to_rule is False  # до отсечки -- освобождена
    assert c.ok is True


def test_vopros_not_immediately_after_klass_fails():
    body = """
**Дата:** 2026-08-09.

**Класс.** Текст класса.

**Ремедиация.** Какое-то другое поле стоит между Класс и Вопрос.

**Вопрос применимости.** Вопрос, но не сразу после Класс.
"""
    c = parse_record("F-NOTADJACENT", body)
    assert c.has_klass is True
    assert c.subject_to_rule is True
    assert c.vopros_present_anywhere is True
    assert c.vopros_immediately_after_klass is False
    assert c.ok is False


def test_vopros_immediately_after_klass_passes():
    body = """
**Дата:** 2026-08-09.

**Факт.** Что-то случилось.

**Класс.** Текст класса.

**Вопрос применимости.** Вопрос сразу после класса.

**Ремедиация.** Не исполнена.
"""
    c = parse_record("F-ADJACENT-OK", body)
    assert c.has_klass is True
    assert c.subject_to_rule is True
    assert c.vopros_immediately_after_klass is True
    assert c.ok is True


def test_klass_multi_paragraph_continuation_still_counts_as_adjacent():
    # регресс на реальную форму F-56/F-59: секция Класс сама состоит из
    # нескольких абзацев прозы (без своих жирных маркеров-полей) -- это
    # ещё Класс, не встрявшее поле; Вопрос сразу после него -- ok.
    body = """
**Дата:** 2026-08-09.

**Класс.** Первый абзац класса.

Второй абзац -- продолжение прозы класса, без своего маркера.

Третий абзац -- то же самое.

**Вопрос применимости.** Вопрос после многоабзацного класса.

**Ремедиация.** Не исполнена.
"""
    c = parse_record("F-MULTIPARA", body)
    assert c.has_klass is True
    assert c.subject_to_rule is True
    assert c.vopros_immediately_after_klass is True
    assert c.ok is True


def test_klass_continuation_then_other_field_before_vopros_fails():
    # symmetric: продолжение прозы Класса легально, но если ПОСЛЕ него
    # встревает ДРУГОЕ поле раньше Вопроса -- всё ещё failed.
    body = """
**Дата:** 2026-08-09.

**Класс.** Первый абзац класса.

Второй абзац -- продолжение прозы класса.

**Ремедиация.** Это поле встряло раньше Вопроса.

**Вопрос применимости.** Вопрос, но уже не сразу после Класс.
"""
    c = parse_record("F-MULTIPARA-FAIL", body)
    assert c.vopros_immediately_after_klass is False
    assert c.ok is False


def test_multiple_blank_lines_between_klass_and_vopros_still_adjacent():
    # несколько пустых строк подряд -- всё ещё "сразу после" (только
    # пустые строки между полями, их количество не лимитировано)
    body = "**Дата:** 2026-08-09.\n\n**Класс.** Текст.\n\n\n\n**Вопрос применимости.** Вопрос.\n"
    c = parse_record("F-MULTIBLANK", body)
    assert c.vopros_immediately_after_klass is True
    assert c.ok is True


def test_unparseable_date_value_treated_as_no_date_fail_closed():
    body = """
**Дата:** не указана.

**Класс.** Текст класса с нечисловой датой.

**Статус.** Открыта.
"""
    c = parse_record("F-BADDATE", body)
    assert c.has_date is False
    assert c.subject_to_rule is True
    assert c.ok is False


# ---------------------------------------------------------------------
# extract_records -- разбор документа по заголовкам.
# ---------------------------------------------------------------------


def test_extract_records_splits_by_header_and_skips_preamble():
    doc = """# Findings

Преамбула с описанием нормы D-0100, упоминающей **Класс.** и
**Вопрос применимости.** только в прозе -- это НЕ запись.

---

## F-1 -- Первая находка

**Класс.** Текст.

## F-2 -- Вторая находка

**Класс.** Текст.
"""
    records = extract_records(doc)
    names = [n for n, _ in records]
    assert names == ["F-1", "F-2"]
    # преамбула не попала ни в одну запись
    assert all("Преамбула" not in body for _, body in records)


# ---------------------------------------------------------------------
# T4 -- живой прогон по настоящему docs/FINDINGS.md.
# ---------------------------------------------------------------------


def _live_records() -> list[tuple[str, str]]:
    text = FINDINGS_PATH.read_text(encoding="utf-8")
    return extract_records(text)


@pytest.mark.parametrize(
    "name,body",
    _live_records(),
    ids=[n for n, _ in _live_records()],
)
def test_live_findings_form(name: str, body: str):
    c = parse_record(name, body)
    assert c.ok, (
        f"{name}: {c.reason} "
        f"(Класс={c.has_klass}, Дата={c.date_value}, "
        f"подпадает={c.subject_to_rule})"
    )
