"""tools/test_claude_binding_guard.py -- машинный сторож рассинхрона
колонки "Model here" таблицы ярусов CLAUDE.md с делегационными
привязками delegation.config.yaml (закрытие открытого остатка d15,
решение Lead 2026-08-20, t-543).

КЛАСС (docs/SIBLING_MAP.md, ':712' "Класс: имя модели прибито как
КРИТЕРИЙ вместо резолюции привязки", заведён 2026-08-16): проверка/
расчёт называет КОНКРЕТНУЮ модель там, где на самом деле имеет в виду
РОЛЬ -- назавтра roles.<роль> в delegation.config.yaml укажет на
другую модель, и место молча соврёт правдоподобным неверным ответом,
не упав. Колонка "Model here" таблицы ярусов CLAUDE.md ("| Function |
Model here | Work | Deliverable |") -- ровно такой носитель: после
перепривязки (пример -- D-0099, Lead Fable->Opus) она рассинхронится
с delegation.config.yaml БЕЗ падения любого существующего теста; цена
класса измерена самим SIBLING_MAP -- прошлая перепривязка прожила в
протоколе калибровки 12 дней и её нашёл не свой чек, а встречный
деплой. Назначение ЭТОГО файла: перепривязка функция->модель видна
КАНОНОМ (python -m pytest tools/ -q), а не молча.

НАХОДКА (сверка спеки с реальностью, правило 3 роли builder): дано
описывало строку Lead как несущую "--" в колонке "Model here"; живой
CLAUDE.md на 2026-08-20 несёт там буквально "Opus" (em-dash стоит в
соседней колонке Deliverable, не в Model here) -- Lead-строка сегодня
ПРОВЕРЯЕТСЯ наравне с остальными (Opus/roles.lead=claude-opus-5,
семейство "opus", совпадает). Инструкция "строка с '--' пропускается"
реализована ОБЩО (по литеральному значению ячейки, не по имени
функции "Lead") -- работает уже сегодня (0 применений) И переживёт
будущий возврат этой ячейки к "--", если он случится.

ПОДХОД к резолюции семейства -- переиспользован (не скопирован
лишний код) из tools/mechanism_gate.py: LEAD_FAMILIES/lead_family()
там резолвят ПОДСТРОКОЙ, регистронезависимо (fable/opus/sonnet/
haiku); этот сторож использует ТОТ ЖЕ приём под собственным именем
(family_of), без ранговой лестницы/skip-деклараций/tier-строк
mechanism_gate -- та машинерия здесь не нужна, сторож делает только
двоичное сравнение "семейство таблицы == семейство конфига".
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO / "CLAUDE.md"
CONFIG_PATH = REPO / "delegation.config.yaml"

TIERS_HEADING_RE = re.compile(r"^##\s+Tiers\b.*$", re.MULTILINE)

# Та же лестница семейств, что LEAD_FAMILIES в tools/mechanism_gate.py --
# порядок здесь не участвует в сравнении (никакой ранговой логики), это
# просто множество распознаваемых семейств.
FAMILIES = ("fable", "opus", "sonnet", "haiku")

# Литеральный em-dash -- ЕДИНСТВЕННОЕ значение ячейки "Model here",
# легально пропускающее строку без резолюции конфига (спека: "строка
# Lead с '--' -- легально пропускается, привязка живёт в конфиге").
# Обычный дефис "-" или пустая ячейка НЕ считаются тем же самым --
# граница п.6а: случайно опустевшая ячейка обязана провалиться как
# несопоставленная привязка, а не молча проскочить мимо сторожа (см.
# test_plain_hyphen_is_not_treated_as_dash_skip ниже).
DASH_SKIP = "—"


def family_of(text: str) -> str | None:
    """Ярусное семейство по подстроке, регистронезависимо (fable/opus/
    sonnet/haiku) -- None, если ни одно семейство не найдено в тексте."""
    low = text.lower()
    for fam in FAMILIES:
        if fam in low:
            return fam
    return None


def parse_tiers_table(claude_md_text: str) -> list[tuple[str, str]]:
    """Строки [(function, model_here)] таблицы ярусов CLAUDE.md.

    Устойчиво к пробелам вокруг "|" (каждая ячейка .strip()-ится).
    Таблица ищется СРАЗУ после заголовка "## Tiers ..." -- пропускаются
    ведущие пустые строки, затем собираются подряд идущие строки,
    начинающиеся на "|" (заголовок колонок и строка-разделитель
    "|---|...|" отбрасываются по содержимому, не по номеру строки);
    первая строка, НЕ начинающаяся на "|" (пустая строка перед прозой
    "Policy rules speak...") естественно останавливает сбор -- конец
    таблицы определяется формой текста, не числом строк/именами
    функций (заголовок секции меняется реже, чем состав таблицы).

    Заголовок секции не найден, или после него нет ни одной "|"-строки
    -- возвращает [] (вызывающий код обязан ПАДАТЬ на пустом результате,
    см. require_nonempty -- молчаливый ноль здесь запрещён спекой)."""
    heading = TIERS_HEADING_RE.search(claude_md_text)
    if not heading:
        return []
    lines = claude_md_text[heading.end():].splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    rows: list[tuple[str, str]] = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        i += 1
        if len(cells) < 2:
            continue
        col1, col2 = cells[0], cells[1]
        if not col1:
            continue
        if col1.lower() == "function":
            continue  # строка заголовка колонок
        if set(col1) <= {"-"}:
            continue  # строка-разделитель |---|---|...
        rows.append((col1, col2))
    return rows


def require_nonempty(rows: list[tuple[str, str]], source_desc: str) -> list[tuple[str, str]]:
    """Молчаливый ноль запрещён (спека п.1): пустой список строк --
    AssertionError с внятным сообщением, не skip и не тихий pass."""
    if not rows:
        raise AssertionError(
            f"Таблица ярусов не найдена / ноль строк распознано в {source_desc} -- "
            "тест ПАДАЕТ (молчаливый ноль запрещён, см. докстринг модуля)."
        )
    return rows


def _resolve_role_model(config_data: dict, role: str) -> str | None:
    role_data = (config_data.get("roles") or {}).get(role) or {}
    if not isinstance(role_data, dict):
        return None
    return ((role_data.get("subscription") or {}).get("model")
            or (role_data.get("api") or {}).get("model"))


def check_bindings(
    rows: list[tuple[str, str]], config_text: str | None
) -> list[tuple[str, str, str | None, str | None, str | None]]:
    """Для каждой строки (function, model_here) резолвит roles.<function>
    живого delegation.config.yaml и сверяет ЯРУСНОЕ СЕМЕЙСТВО.

    config_text отсутствует/пуст/не парсится -- ValueError (fail-closed
    по спеке п.3: "в этом деплое конфиг обязан быть" -- НЕ дефолт вроде
    mechanism_gate.resolve_lead_binding's "fable", сторож здесь не
    приемлет тихого дефолта вообще).

    Возвращает список mismatch-кортежей (function, table_model,
    config_model, table_family, config_family) -- пустой список значит
    "все строки совпали". Несовпадение фиксируется когда: config_model
    отсутствует (роль не сконфигурирована), ЛИБО семейство одной из
    сторон не распознано, ЛИБО оба распознаны, но не равны."""
    if not config_text:
        raise ValueError(
            "delegation.config.yaml пуст или отсутствует -- fail-closed: "
            "в этом деплое конфиг обязан нести привязки (спека п.3)."
        )
    try:
        data = yaml.safe_load(config_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"delegation.config.yaml не парсится: {exc}") from exc
    if not isinstance(data.get("roles"), dict):
        raise ValueError("delegation.config.yaml: ключ roles отсутствует или не словарь.")

    mismatches: list[tuple[str, str, str | None, str | None, str | None]] = []
    for function, model_here in rows:
        if model_here == DASH_SKIP:
            # Легальный пропуск (спека п.2): привязка живёт в конфиге,
            # ячейка сознательно не дублирует имя модели.
            continue
        role = function.strip().lower()
        table_fam = family_of(model_here)
        config_model = _resolve_role_model(data, role)
        config_fam = family_of(config_model) if config_model else None
        if config_model is None or table_fam is None or table_fam != config_fam:
            mismatches.append((function, model_here, config_model, table_fam, config_fam))
    return mismatches


def format_mismatches(mismatches: list[tuple]) -> str:
    lines = ["Рассинхрон таблицы ярусов CLAUDE.md с delegation.config.yaml:"]
    for function, table_model, config_model, table_fam, config_fam in mismatches:
        lines.append(
            f"  {function}: Model here={table_model!r} (семейство {table_fam!r}) "
            f"vs roles.{function.lower()}={config_model!r} (семейство {config_fam!r})"
        )
    return "\n".join(lines)


# --- живая пара (DoD п.1) ------------------------------------------------

def test_live_tiers_table_matches_config_bindings():
    """Живой CLAUDE.md против живого delegation.config.yaml -- ноль
    рассинхронов на момент посадки (scout/builder=Sonnet,
    critic/designer=Opus, Lead=Opus -- сверено фактом конфига, не
    памятью, см. докстринг "НАХОДКА")."""
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    rows = require_nonempty(parse_tiers_table(claude_text), str(CLAUDE_MD))
    config_text = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else None
    mismatches = check_bindings(rows, config_text)
    assert mismatches == [], format_mismatches(mismatches)


# --- красная половина 1: синтетический рассинхрон (DoD п.2) -------------

def test_red_synthetic_mismatch_is_caught():
    """Синтетическая пара таблица/конфиг с намеренным расхождением
    (builder=Opus в таблице, но roles.builder=claude-sonnet-5 в
    конфиге) -- сторож обязан её поймать, поимённо."""
    rows = [("scout", "Sonnet"), ("builder", "Opus")]
    config_text = (
        "roles:\n"
        "  scout:\n"
        "    subscription:\n"
        "      model: claude-sonnet-5\n"
        "  builder:\n"
        "    subscription:\n"
        "      model: claude-sonnet-5\n"
    )
    mismatches = check_bindings(rows, config_text)
    assert len(mismatches) == 1, format_mismatches(mismatches)
    function, table_model, config_model, table_fam, config_fam = mismatches[0]
    assert function == "builder"
    assert table_model == "Opus"
    assert config_model == "claude-sonnet-5"
    assert table_fam == "opus"
    assert config_fam == "sonnet"


# --- красная половина 2: таблица без единой распознанной строки (DoD п.2) -

def test_red_table_with_no_recognized_rows_fails_loudly():
    """CLAUDE.md-подобный текст, несущий заголовок секции, но НИ ОДНОЙ
    table-строки -- parse_tiers_table() возвращает [], require_nonempty()
    ПАДАЕТ с внятным сообщением (не skip, не молчаливый True)."""
    synthetic_text = (
        "## Tiers — functions, not models (D-0062)\n\n"
        "Prose only, no table survives here at all.\n"
    )
    rows = parse_tiers_table(synthetic_text)
    assert rows == []
    with pytest.raises(AssertionError, match="Таблица ярусов не найдена"):
        require_nonempty(rows, "synthetic")


def test_red_missing_heading_also_yields_empty_rows():
    """Соседний край того же красного случая: секция "## Tiers" вообще
    отсутствует в тексте -- тот же пустой результат, та же обязанность
    упасть у require_nonempty (не отдельная незамеченная ветка)."""
    rows = parse_tiers_table("No Tiers heading anywhere in this text.\n")
    assert rows == []
    with pytest.raises(AssertionError):
        require_nonempty(rows, "synthetic-no-heading")


# --- fail-closed на отсутствующем/битом конфиге (DoD п.3) ----------------

def test_missing_config_fails_closed_not_silent_default():
    """config_text=None (файл отсутствует) -- ValueError, НЕ тихий
    дефолт (в отличие от mechanism_gate.resolve_lead_binding's "fable")
    -- этот деплой обязан нести привязки (спека п.3)."""
    with pytest.raises(ValueError, match="fail-closed"):
        check_bindings([("scout", "Sonnet")], None)


def test_unparsable_config_fails_closed():
    with pytest.raises(ValueError, match="не парсится"):
        check_bindings([("scout", "Sonnet")], "roles: [this is not a mapping\n")


def test_config_without_roles_key_fails_closed():
    with pytest.raises(ValueError, match="roles"):
        check_bindings([("scout", "Sonnet")], "unrelated: true\n")


# --- граница DASH_SKIP (правило 6а: тест на границе и за ней) ------------

def test_dash_row_is_legally_skipped_without_config_entry():
    """Em-dash ровно -- легальный пропуск (спека п.2): строка проходит
    БЕЗ требования наличия roles.<function> в конфиге вовсе."""
    rows = [("lead", DASH_SKIP)]
    mismatches = check_bindings(rows, "roles: {}\n")
    assert mismatches == []


def test_plain_hyphen_is_not_treated_as_dash_skip():
    """ГРАНИЦА: обычный дефис "-" (не em-dash) -- НЕ легальный пропуск.
    Случайно опустевшая/испорченная ячейка обязана провалиться как
    несопоставленная привязка, не проскочить молча мимо сторожа."""
    rows = [("lead", "-")]
    mismatches = check_bindings(rows, "roles: {}\n")
    assert len(mismatches) == 1
    assert mismatches[0][0] == "lead"


def test_empty_cell_is_not_treated_as_dash_skip():
    """Тот же класс границы: пустая ячейка тоже не проскакивает."""
    rows = [("lead", "")]
    mismatches = check_bindings(rows, "roles: {}\n")
    assert len(mismatches) == 1


# --- парсер устойчив к пробелам вокруг "|" (спека п.1) --------------------

def test_parser_is_whitespace_tolerant():
    text = (
        "## Tiers — functions, not models (D-0062)\n\n"
        "|Function|Model here|Work|Deliverable|\n"
        "|---|---|---|---|\n"
        "|  scout   |   Sonnet   | recon | digest |\n"
    )
    rows = parse_tiers_table(text)
    assert rows == [("scout", "Sonnet")]
