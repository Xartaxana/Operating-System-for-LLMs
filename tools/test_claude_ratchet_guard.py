"""tools/test_claude_ratchet_guard.py -- сторож порогов ядра
CLAUDE_WARN/CLAUDE_BREACH (ось 14, экземпляр 2, породы "порог, выведенный
формулой от замера, с претензией на монотонность"; спека t-575,
2026-08-20, docs/tasks/2026-08-20_claude-ratchet-guard-spec.md).

НОРМА (§2 спеки, дословно): ХРАПОВИК ЯДРА. CLAUDE_WARN -- не константа
проекта, а ФУНКЦИЯ ЗАМЕРА: WARN = ceil(size(CLAUDE.md) x 1.015 / 100) x
100, где size -- размер файла на диске (тот же замер, что печатает
суффикс SessionStart). (1) СНИЖЕНИЕ ЛЕГАЛЬНО ВСЕГДА И МОЛЧА. После
диеты порог перевыводится тем же выражением: ни слова оператора, ни
события. Снижать -- бесплатно. (2) ПОДЪЁМ ЛЕГАЛЕН, ТОЛЬКО ЕСЛИ ЕГО УЖЕ
ОПЛАТИЛ ЗАМЕР. Новый порог не выше потолка от РАЗМЕРА ФАЙЛА НА МОМЕНТ
ПОДЪЁМА. Подъём про запас невозможен не по запрету, а по арифметике:
чтобы поднять порог, надо СНАЧАЛА иметь байты. С пробитого 37500
следующий легальный потолок -- 38100 (+600 Б), не больше. (3) K = 1.015
-- ЧАСТЬ НОРМЫ, не параметр реализации. Другой K -- смена правила
вывода: отдельное решение оператора и отдельная правка литерального
пина. (4) СЛОВО ОПЕРАТОРА дописывается в комментарий-провенанс
ПРИСТРОЙКОЙ; прежние абзацы не переписываются. Молчаливый подъём --
отказ механизма. ПРОСАДКА (WARN выше потолка) -- не нарушение, а ДОЛГ:
объявляет себя строкой в КАЖДОМ SessionStart, пока не снята
перевыводом.

ПОЧЕМУ КОНСТРУКЦИЯ ДРУГАЯ, чем у сторожа гейта (а) (test_gate_a_history_
monotonic и его семья): база формулы здесь не ОБЪЯВЛЯЕТСЯ, а ИЗМЕРЯЕТСЯ
-- stat().st_size живого CLAUDE.md, тот же замер, что уже печатает
суффикс SessionStart. Число, которое нельзя подделать, нельзя и
подогнать -- поэтому здесь нет истории записей, блока provenance-полей
и калитки аннулирования: подделывать нечего. Копировать форму брата
было бы карго-культом (см. §1 спеки).

Числа CLAUDE_WARN/CLAUDE_BREACH этим узлом НЕ ТРОГАЮТСЯ (К1 приёмки) --
модуль ставит СТОРОЖА норме, а не двигает порог.
"""
from __future__ import annotations

import math

import pytest

import session_context as sc

# --- 1. позитивный контроль на реальной истории провенанса ---------------


def test_ceiling_reproduces_recorded_derivations():
    """Обе исторические перевыводки провенанс-комментария session_context.py
    воспроизводятся функцией: W2c-4 (36102 -> 36700) и Р-О4 (36900 ->
    37500). Живая формула обязана сходиться с тем, что уже записано
    прозой."""
    assert sc.claude_warn_ceiling(36102) == 36700
    assert sc.claude_warn_ceiling(36900) == 37500


# --- 2. таблица независимых литералов (урок атаки 4 блокера t-569) -------


def test_ceiling_literal_table():
    """К из модуля НЕ импортируется в ожидания -- каждое значение
    прописано отдельным литералом, посчитанным вручную от нормы §2
    (ceil(size*1.015/100)*100), а не вызовом с константой модуля.
    Тест, берущий K из модуля, доказывает самосогласованность, а не
    норму -- ровно то, что не поймало атаку 4 у брата."""
    table = [
        (0, 0),
        (1, 100),
        (50, 100),
        (100, 200),
        (200, 300),
        (20000, 20300),
        (40000, 40600),
        (36847, 37400),
        (36848, 37500),
        (36998, 37600),
    ]
    for size, expected in table:
        assert sc.claude_warn_ceiling(size) == expected, (
            f"claude_warn_ceiling({size}) = {sc.claude_warn_ceiling(size)}, "
            f"ожидание независимого литерала = {expected}"
        )


# --- 3. ловушка двоичного округления на точных кратных -------------------


def test_ceiling_integer_form_matches_float_form_on_exact_multiples():
    """20000 и 40000 -- точные кратные, на которых двоичное округление
    float-формы формулы могло бы разойтись с целой арифметикой
    claude_warn_ceiling(). Литерал 1.015 в этом тесте НЕЗАВИСИМЫЙ (не
    K из модуля) -- сверяются ДВЕ независимо записанные формы одной
    формулы, не самосогласованность."""
    for size in (20000, 40000):
        float_form = int(math.ceil(size * 1.015 / 100) * 100)
        assert sc.claude_warn_ceiling(size) == float_form


# --- 4. пин K (сообщение = пункт (3) нормы дословно) ----------------------


def test_k_permille_literal_pin():
    assert sc.CLAUDE_WARN_K_PERMILLE == 1015, (
        "K = 1.015 -- ЧАСТЬ НОРМЫ, не параметр реализации. Другой K -- "
        "смена правила вывода: отдельное решение оператора и отдельная "
        "правка литерального пина (норма §2 п.3)."
    )


# --- 5. пин WARN/BREACH (сообщение = вся норма §2 дословно) --------------


def test_claude_warn_and_breach_literal_pin():
    assert (sc.CLAUDE_WARN, sc.CLAUDE_BREACH) == (37500, 37800), (
        "ХРАПОВИК ЯДРА. CLAUDE_WARN -- не константа проекта, а ФУНКЦИЯ "
        "ЗАМЕРА: WARN = ceil(size(CLAUDE.md) x 1.015 / 100) x 100, где "
        "size -- размер файла на диске (тот же замер, что печатает "
        "суффикс SessionStart). (1) СНИЖЕНИЕ ЛЕГАЛЬНО ВСЕГДА И МОЛЧА. "
        "После диеты порог перевыводится тем же выражением: ни слова "
        "оператора, ни события. Снижать -- бесплатно. (2) ПОДЪЁМ ЛЕГАЛЕН, "
        "ТОЛЬКО ЕСЛИ ЕГО УЖЕ ОПЛАТИЛ ЗАМЕР. Новый порог не выше потолка от "
        "РАЗМЕРА ФАЙЛА НА МОМЕНТ ПОДЪЁМА. Подъём про запас невозможен не "
        "по запрету, а по арифметике: чтобы поднять порог, надо СНАЧАЛА "
        "иметь байты. С пробитого 37500 следующий легальный потолок -- "
        "38100 (+600 Б), не больше. (3) K = 1.015 -- ЧАСТЬ НОРМЫ, не "
        "параметр реализации. Другой K -- смена правила вывода: отдельное "
        "решение оператора и отдельная правка литерального пина. "
        "(4) СЛОВО ОПЕРАТОРА дописывается в комментарий-провенанс "
        "ПРИСТРОЙКОЙ; прежние абзацы не переписываются. Молчаливый подъём "
        "-- отказ механизма. ПРОСАДКА (WARN выше потолка) -- не нарушение, "
        "а ДОЛГ: объявляет себя строкой в КАЖДОМ SessionStart, пока не "
        "снята перевыводом. Вы правите порог ядра: снижение -- молча и "
        "бесплатно; подъём -- по пунктам (2)-(4)."
    )


# --- 6. отношение BREACH = WARN + 300 -------------------------------------


def test_claude_breach_is_warn_plus_300():
    assert sc.CLAUDE_BREACH == sc.CLAUDE_WARN + 300


# --- 7. граница просадки: 36848 зелёный, 36847 красный (правило 6а) ------


def test_sag_boundary_36848_green_36847_red(tmp_path):
    """Граница ЭТОЙ узловой правки, а не WARN-порога boot_budget_lines()
    самого: на этих размерах claude_size < CLAUDE_WARN всегда (OVER не
    участвует), маркер SAG переключается РОВНО на границе потолка."""
    root = tmp_path
    (root / "CLAUDE.md").write_bytes(b"x" * 36848)
    lines_green = sc.boot_budget_lines(root)
    assert "RATCHET SAG" not in lines_green[0]

    (root / "CLAUDE.md").write_bytes(b"x" * 36847)
    lines_red = sc.boot_budget_lines(root)
    assert "RATCHET SAG" in lines_red[0]
    assert "RATCHET SAG 100 B: WARN 37500 > ceil(36847*1.015) = 37400" in lines_red[0]


# --- 8. OVER и SAG взаимно исключены --------------------------------------


def test_sag_and_over_mutually_exclusive(tmp_path):
    """По диапазону размеров (включая переход через CLAUDE_WARN):
    ceiling(size) >= size*1.015 >= size, значит size > WARN подразумевает
    ceiling(size) > WARN -- OVER и SAG не могут гореть на одной строке."""
    root = tmp_path
    for size in (0, 1, 100, 20000, 36847, 36848, 37500, 37501, 40000, 100000):
        (root / "CLAUDE.md").write_bytes(b"x" * size)
        line = sc.boot_budget_lines(root)[0]
        over = "OVER" in line
        sag = "RATCHET SAG" in line
        assert not (over and sag), f"size={size}: OVER и SAG сработали ОБА в одной строке: {line!r}"


# --- 9. missing-мир байт в байт -------------------------------------------


def test_missing_claude_md_no_sag_marker(tmp_path):
    """Мир missing печатается БАЙТ В БАЙТ как до этой правки -- инвариант
    позиции спеки: ветка SAG стоит ВНУТРИ не-missing else, missing-мир её
    не видит вовсе."""
    root = tmp_path
    lines = sc.boot_budget_lines(root)
    assert lines[0] == (
        "BOOT BUDGET: 0 bytes / 100000 (1 files) [missing: CLAUDE.md]"
        " | CLAUDE.md: missing"
    )
    assert "RATCHET SAG" not in lines[0]


# --- 10. нулевой байт -> максимальная просадка (анти-атака 5б) -----------


def test_zero_byte_claude_md_maximal_sag(tmp_path):
    """Пустой CLAUDE.md (0 байт, файл СУЩЕСТВУЕТ -- не missing): потолок
    0, просадка = ВЕСЬ WARN. Прямая инверсия атаки 5б блокера t-569, где
    нулевой замер ГАСИЛ проверку -- здесь он делает её МАКСИМАЛЬНО
    строгой."""
    root = tmp_path
    (root / "CLAUDE.md").write_bytes(b"")
    lines = sc.boot_budget_lines(root)
    assert f"RATCHET SAG {sc.CLAUDE_WARN} B: WARN {sc.CLAUDE_WARN} > ceil(0*1.015) = 0" in lines[0]


# --- 11. WIRING на живом корне (доказывает проводку, НЕ корректность) ----


def test_live_boot_line_marker_matches_recomputed_ceiling():
    """ЯВНО: этот тест доказывает, что boot_budget_lines() на живом
    CLAUDE.md действительно ЗОВЁТ claude_warn_ceiling() и печатает его
    результат (проводка) -- корректность самой формулы уже доказана
    тестами 1-3 на литералах, не здесь. Иначе это зарегистрированный
    класс "сторож читает только собственный след"."""
    root = sc.repo_root()
    claude_size = (root / "CLAUDE.md").stat().st_size
    ceiling = sc.claude_warn_ceiling(claude_size)
    lines = sc.boot_budget_lines(root)
    live_suffix_line = lines[0]
    assert f"CLAUDE.md: {claude_size}/{sc.CLAUDE_WARN}" in live_suffix_line
    if sc.CLAUDE_WARN > ceiling:
        assert (
            f"RATCHET SAG {sc.CLAUDE_WARN - ceiling} B: WARN {sc.CLAUDE_WARN}"
            f" > ceil({claude_size}*1.015) = {ceiling} -> re-derive (lower is free)"
        ) in live_suffix_line
    else:
        assert "RATCHET SAG" not in live_suffix_line


# --- 12. красные половины --------------------------------------------------


def test_guard_discriminates_wrong_k(monkeypatch):
    """Красная половина: монки-патч K=1.2 (промилле 1200) -- таблица
    независимых литералов (см. test_ceiling_literal_table) обязана
    РАСХОДИТЬСЯ с пересчётом под неверным K. Ровно атака 4 блокера t-569:
    сторож обязан отличать K=1.015 от K=1.2, а не быть самосогласованным
    с чем угодно, что стоит в модуле."""
    monkeypatch.setattr(sc, "CLAUDE_WARN_K_PERMILLE", 1200)
    correct_table = [
        (0, 0), (1, 100), (50, 100), (100, 200), (200, 300),
        (20000, 20300), (40000, 40600),
        (36847, 37400), (36848, 37500), (36998, 37600),
    ]
    mismatches = [
        (size, expected, sc.claude_warn_ceiling(size))
        for size, expected in correct_table
        if sc.claude_warn_ceiling(size) != expected
    ]
    assert mismatches, "монки-патч K=1.2 обязан разойтись хотя бы на одном литерале таблицы"


def test_guard_discriminates_raised_warn(tmp_path, monkeypatch):
    """Красная половина: монки-патч CLAUDE_WARN=525000 (подъём, который
    замер НЕ оплатил) -- маркер печатается с ДОСЛОВНОЙ подстрокой
    'RATCHET SAG' немедленно, на обычном размере файла. Живой CLAUDE.md
    НЕ портится -- корёжится только константа в памяти процесса (гигиена
    п.7(г)); monkeypatch откатывает её сам по завершении теста."""
    monkeypatch.setattr(sc, "CLAUDE_WARN", 525000)
    root = tmp_path
    (root / "CLAUDE.md").write_bytes(b"x" * 36998)
    lines = sc.boot_budget_lines(root)
    assert "RATCHET SAG" in lines[0]


# --- адверсариальная батарея (D-0054 п.е, вход -- файловая система) ------


def test_adversarial_size_bytes_none_string_nan_yield_zero_ceiling():
    """size_bytes как None/строка/nan -> 0 (fail-closed)."""
    assert sc.claude_warn_ceiling(None) == 0
    assert sc.claude_warn_ceiling("not a number") == 0
    assert sc.claude_warn_ceiling(float("nan")) == 0


def test_adversarial_negative_size_yields_zero_ceiling():
    assert sc.claude_warn_ceiling(-1) == 0
    assert sc.claude_warn_ceiling(-36998) == 0


def test_adversarial_unreadable_claude_md_treated_as_missing(tmp_path, monkeypatch):
    """OSError при stat() (симулирует нечитаемый файл) -- ветка missing,
    как и для по-настоящему отсутствующего файла; boot_budget_lines()
    уже несёт этот try/except общо (не добавлен этим узлом), тест
    фиксирует, что SAG-ветка его не обходит."""
    root = tmp_path
    target = (root / "CLAUDE.md")
    target.write_bytes(b"x" * 100)
    real_stat = type(target).stat

    def _boom(self, *a, **kw):
        if self == target:
            raise OSError("simulated unreadable file")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(type(target), "stat", _boom)
    lines = sc.boot_budget_lines(root)
    assert "[missing: CLAUDE.md]" in lines[0]
    assert "RATCHET SAG" not in lines[0]


def test_adversarial_directory_named_claude_md_does_not_crash(tmp_path):
    """Каталог с именем CLAUDE.md вместо файла -- поведение НАЗВАНО и
    запинено как приемлемая странность, НЕ крэш: Path.stat() на
    каталоге не бросает OSError на Windows/POSIX, значит код идёт по
    не-missing ветке с размером каталога (платформенно-зависимое малое
    число, не содержимым)."""
    root = tmp_path
    (root / "CLAUDE.md").mkdir()
    lines = sc.boot_budget_lines(root)  # не должно бросить исключение
    assert "CLAUDE.md:" in lines[0]
    assert "missing" not in lines[0]


def test_adversarial_symlink_claude_md_follows_target_size(tmp_path):
    """Симлинк -- stat() следует по ссылке (названо). Windows без
    Developer Mode/повышенных прав может запретить создание симлинков --
    тест сам себя пропускает по OSError создания, не изображает
    прохождение проверки, которой не было."""
    target = tmp_path / "real_claude_target.md"
    target.write_bytes(b"x" * 12345)
    link = tmp_path / "CLAUDE.md"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable in this environment: {exc}")
    lines = sc.boot_budget_lines(tmp_path)
    assert "CLAUDE.md: 12345/37500" in lines[0]


def test_adversarial_ten_megabyte_claude_md_does_not_crash(tmp_path):
    """Файл 10 МБ -- не крэш, классифицируется OVER (не SAG, потолок от
    10 МБ огромен)."""
    root = tmp_path
    ten_mb = 10 * 1024 * 1024
    (root / "CLAUDE.md").write_bytes(b"x" * ten_mb)
    lines = sc.boot_budget_lines(root)
    assert f"CLAUDE.md: {ten_mb}/{sc.CLAUDE_WARN} OVER" in lines[0]
    assert "RATCHET SAG" not in lines[0]


def test_adversarial_claude_warn_zero_named_hole(tmp_path, monkeypatch):
    """CLAUDE_WARN=0 (монки-патч) -- маркер SAG НЕ печатается, потому что
    ceiling(size>0) > 0 = WARN всегда; всё и так OVER. НАЗВАННАЯ ДЫРА
    (спека §5 п.12/адверс. батарея, §3 строка СБРОС): ловится отдельным
    пином test_claude_warn_and_breach_literal_pin, не этим тестом."""
    monkeypatch.setattr(sc, "CLAUDE_WARN", 0)
    root = tmp_path
    (root / "CLAUDE.md").write_bytes(b"x" * 100)
    lines = sc.boot_budget_lines(root)
    assert "RATCHET SAG" not in lines[0]
    assert "OVER" in lines[0]


def test_adversarial_claude_warn_negative_named_hole(tmp_path, monkeypatch):
    """Тот же класс, отрицательный WARN: ceiling(size>=0) >= 0 всегда, а
    WARN < 0 < ceiling -- SAG-условие (WARN > ceiling) ложно."""
    monkeypatch.setattr(sc, "CLAUDE_WARN", -1)
    root = tmp_path
    (root / "CLAUDE.md").write_bytes(b"x" * 100)
    lines = sc.boot_budget_lines(root)
    assert "RATCHET SAG" not in lines[0]
