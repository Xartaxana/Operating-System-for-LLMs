"""tools/test_warn_messages.py -- УЗЕЛ C (docs/tasks/2026-08-25_
warn-class-fix-dag.md, "УЗЕЛ C -- читаемость: варн называет три вещи и
разделяет случаи"). Машинная проверка формы (C-К4) шести сиблингов
_msg.py, ПАРАМЕТРИЗОВАННАЯ СИБЛИНГАМИ (шесть носителей, а не литералами
теста) -- каждая проверка ЧИТАЕТ актуальный текст ИЗ модуля (importlib
на сиблинг, если он существует, иначе живой файл -- тот же f61-паттерн,
что tools/test_dispatch_gate_md.py уже несёт, temporal-край 5.4
родительской спеки: до посадки прогон не падает FileNotFoundError; после
посадки байт-копией сиблинг снимается, прогон молча переключается на
живой файл, который к тому моменту несёт тот же текст).

Узел C НЕ владеет tools/warn_layers.json (поправка Lead 2026-08-25:
реестр исключён из owns, патч -- отдельной секцией отчёта билдера,
применяет Lead на посадке) -- этот файл его только ЧИТАЕТ.

ОХВАТ (C-К3, 13 записей реестра из шести носителей узла C -- пять
GIVEN-PATH/ROLE-TYPE/WRITE-QUOTED/DOD-QUOTED/MANIFEST-QUOTED узла A НЕ
входят, carrier=dispatch_gate.py): OWNS_OVERLAP, BLIND_OWNS, QUOTED_OWNS
(owns_gate_msg.py); NOTES_LEN, TIER_ECHO, WITNESS_ECHO, TS_DRIFT,
R6_ZERKALO, JOURNAL_ECHO_BASE (journal_echo_msg.py); NEGATIVE_LINT
(negative_lint_msg.py); NEGATIVE_CLAIM (claim_control_gate_msg.py);
SEARCH_RETURNED_NOTHING (search_control_gate_msg.py); HYGIENE
(hygiene_gate_msg.py). JOURNAL_ECHO_BASE намеренно исключён из
verb-проверки -- см. докстринг build_context в journal_echo_msg.py
("УЗЕЛ C ... НЕ ПРАВИТСЯ этим узлом"), содержательная часть живёт в
tools/journal_validator.py, вне owns узла C (R9-находка для координатора).

Run:  python -m pytest tools/test_warn_messages.py -q
Негативный контроль (C-К4, обязателен): test_verb_checker_negative_control_*
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

WARN_LAYERS_PATH = TOOLS_DIR / "warn_layers.json"


def _load_module(msg_name: str, live_name: str, alias: str):
    """f61-форма (temporal-край 5.4 родительской спеки): сиблинг
    _msg.py, ЕСЛИ существует, иначе живой файл -- тот же принцип, что
    tools/test_dispatch_gate_md.py._resolve_script_path() уже несёт для
    узла A. До посадки -- сиблинг (новые тексты); после посадки байт-
    копией сиблинг снимается, прогон молча берёт живой файл (тот же
    текст, посадка синхронна)."""
    sib = TOOLS_DIR / msg_name
    path = sib if sib.exists() else TOOLS_DIR / live_name
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owns_gate = _load_module("owns_gate_msg.py", "owns_gate.py", "owns_gate_wm")
journal_echo = _load_module("journal_echo_msg.py", "journal_echo.py", "journal_echo_wm")
negative_lint = _load_module("negative_lint_msg.py", "negative_lint.py", "negative_lint_wm")
claim_control_gate = _load_module(
    "claim_control_gate_msg.py", "claim_control_gate.py", "claim_control_gate_wm"
)
search_control_gate = _load_module(
    "search_control_gate_msg.py", "search_control_gate.py", "search_control_gate_wm"
)
hygiene_gate = _load_module("hygiene_gate_msg.py", "hygiene_gate.py", "hygiene_gate_wm")


@pytest.fixture(scope="session")
def registry():
    with WARN_LAYERS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _layer(registry_data, layer_id):
    for layer in registry_data["layers"]:
        if layer["id"] == layer_id:
            return layer
    raise KeyError(layer_id)


# ---------------------------------------------------------------------
# Рендер актуальных текстов -- КАЖДЫЙ вызывает функцию/константу ИЗ
# модуля (не копирует текст в тело теста, C-К4 буквально).
# ---------------------------------------------------------------------


def _render_owns_overlap() -> str:
    records = [
        {
            "ts": "2026-08-25T10:00:00",
            "session_key": "other-session",
            "cwd": "D:/repo",
            "description": "другой диспатч",
            "owns": ["tools/x.py"],
        }
    ]
    grouped = owns_gate._find_overlaps(["tools/x.py"], records, "this-session")
    return owns_gate._format_overlap_context(grouped)


def _render_tier_echo(kind: str) -> str:
    if kind == "mismatch":
        event = (2, "mismatch", "sonnet", {"claude-opus-4-8": 1})
    else:
        event = (2, "info", "sonnet", {"claude-fable-1": 1, "claude-sonnet-5": 1})
    return journal_echo._format_tier_line(event, ascii_only=False)


def _render_witness_echo(kind: str) -> str:
    if kind == "warn_loud":
        event = ("warn_loud", 2, "pytest -q", "2026-08-25T10:00:00")
    elif kind == "warn_stale":
        event = ("warn_stale", 2, "2026-08-25T10:00:00", "2026-08-24T09:00:00")
    else:
        event = ("warn_soft", 2)
    return journal_echo._format_witness_line(event, ascii_only=False)


def _render_ts_drift(kind: str) -> str:
    delta = 5 if kind == "future" else -5
    return journal_echo._format_ts_drift_line((2, kind, delta))


def _render_r6_zerkalo() -> str:
    event = (2, "trigger", "t-042", "2 of 2")
    return journal_echo._format_escalation_line(event, ascii_only=False)


def _render_notes_len() -> str:
    return journal_echo._format_notes_len_line((2, "delegated", 900, 800))


def _render_negative_lint() -> str:
    return negative_lint.format_warning([(3, "негативная строка примера")])


def _render_negative_claim() -> str:
    return claim_control_gate.MSG_TEMPLATE.format(tokens="x.py")


def _render_search_returned_nothing() -> str:
    return search_control_gate.MSG


def _render_hygiene(name: str) -> str:
    return getattr(hygiene_gate, name)


def _render_hygiene_wrapped() -> str:
    # тот же паттерн склейки, что decide() -- проверка ПРЕФИКСА реестра
    # (см. test_hygiene_wrapped_prefix ниже).
    return "Командная гигиена (WARN, не блокирует): " + hygiene_gate.MSG_CD_PREFIX


# ---------------------------------------------------------------------
# C-К4 (1/4): повелительный глагол из ЗАКРЫТОГО перечня. Перечень --
# СОБСТВЕННАЯ мех. конструкция теста (per-слойный набор ожидаемых
# глаголов, ровно те, что билдер вписал в тексты -- не проектное
# решение, а перечисление факта), НЕ копирует тело сообщения целиком.
# ---------------------------------------------------------------------

_VERB_CASES = [
    ("OWNS_OVERLAP", _render_owns_overlap, {"сериализуй", "разведи"}),
    (
        "BLIND_OWNS",
        lambda: owns_gate.BLIND_OWNS_WARN_MESSAGE,
        {"проверь"},
    ),
    (
        "QUOTED_OWNS",
        lambda: owns_gate.QUOTED_OWNS_WARN_MESSAGE,
        {"перенеси"},
    ),
    ("NOTES_LEN", _render_notes_len, {"move", "keep"}),
    ("TIER_ECHO/mismatch", lambda: _render_tier_echo("mismatch"), {"сверь"}),
    ("TIER_ECHO/info", lambda: _render_tier_echo("info"), {"сверь"}),
    ("WITNESS_ECHO/warn_loud", lambda: _render_witness_echo("warn_loud"), {"re-run"}),
    ("WITNESS_ECHO/warn_stale", lambda: _render_witness_echo("warn_stale"), {"re-run"}),
    ("WITNESS_ECHO/warn_soft", lambda: _render_witness_echo("warn_soft"), {"verify"}),
    ("TS_DRIFT/future", lambda: _render_ts_drift("future"), {"note", "read"}),
    ("TS_DRIFT/stale", lambda: _render_ts_drift("stale"), {"note", "read"}),
    ("R6_ZERKALO", _render_r6_zerkalo, {"эскалируй", "допиши"}),
    ("NEGATIVE_LINT", _render_negative_lint, {"добавь", "перепроверь"}),
    ("NEGATIVE_CLAIM", _render_negative_claim, {"run"}),
    ("SEARCH_RETURNED_NOTHING", _render_search_returned_nothing, {"run"}),
    ("HYGIENE/MSG_CD_PREFIX", lambda: _render_hygiene("MSG_CD_PREFIX"), {"вызывай"}),
    ("HYGIENE/MSG_REDIRECT_STDERR", lambda: _render_hygiene("MSG_REDIRECT_STDERR"), {"убери"}),
    ("HYGIENE/MSG_PYTHON_DASH_C", lambda: _render_hygiene("MSG_PYTHON_DASH_C"), {"используй"}),
    ("HYGIENE/MSG_CD_NON_ROOT_WARN", lambda: _render_hygiene("MSG_CD_NON_ROOT_WARN"), {"вызывай"}),
]


def _contains_imperative_verb(text: str, verbs: set) -> bool:
    """Закрытый перечень -- case-sensitive-нечувствительный поиск ЛЮБОГО
    глагола набора КАК ПОДСТРОКИ (набор специфичен по слою -- дешёвая
    форма, не претендует на морфологию всего языка)."""
    low = text.lower()
    return any(v.lower() in low for v in verbs)


@pytest.mark.parametrize(
    "name,render,verbs", _VERB_CASES, ids=[c[0] for c in _VERB_CASES]
)
def test_c4_imperative_verb_present(name, render, verbs):
    text = render()
    assert _contains_imperative_verb(text, verbs), f"{name}: {text!r} несёт ни одного из {verbs}"


def test_verb_checker_negative_control_text_without_verb_fails():
    """C-К4 буквально: "текст без глагола -> тест краснеет". Проверяет
    САМ чекер (не реальную константу) -- синтетическая строка без
    единого повелительного глагола из набора обязана дать False."""
    bad_text = "путь не найден, состояние неизвестно, реестр молчит"
    assert not _contains_imperative_verb(bad_text, {"проверь", "исправь", "run", "verify"})


def test_verb_checker_positive_control_text_with_verb_passes():
    # позитивный контроль в паре (командная гигиена п.6) -- тот же
    # checker, форма текста та же, глагол присутствует.
    good_text = "путь не найден \u2014 проверь форму owns-строки"
    assert _contains_imperative_verb(good_text, {"проверь", "исправь"})


# ---------------------------------------------------------------------
# C-К4 (2/4): длина в границах бюджета -- М2-4 (docs/tasks/2026-08-25_
# kopilka-wave-spec.md, "БИЛДЕР М2", снимает заглушку выше): Р-С1
# (числовой бюджет длины) НАЗНАЧЕН Lead'ом ДО диспатча -- ХРАПОВИК 550
# символов на СООБЩЕНИЕ (docs/tasks/2026-08-25_kopilka-wave-spec.md,
# "Решения Lead, принятые до диспатча"; носитель счёта --
# len() живых констант этой же батареи — замер воспроизводим самим
# тестом, внешнего носителя нет; снимок 2026-08-25, max 513; строка
# оси 14 docs/SIBLING_MAP.md — подъём без нового замера = находка).
#
# Замер ЭТОГО builder'а (независимая перепроверка ТЕМ ЖЕ составом --
# battery = _VERB_CASES выше, 18 записей: константы И отформатированные
# образцы, тот же список, что уже несёт C-К4 (1/4) verb-проверку выше --
# не отдельная выборка): максимум 513 символов (HYGIENE/
# MSG_CD_NON_ROOT_WARN), второй по величине 484 (SEARCH_RETURNED_NOTHING),
# хвост остальных 16 записей -- 129..301. Числа СОВПАДАЮТ с заявленными
# в спеке буквально (максимум 513, второй 484, хвост 130-305 -- в этом
# прогоне нижняя граница хвоста оказалась 129, не 130 -- BLIND_OWNS,
# see below; расхождение на 1 символ не меняет вывод "бюджет 550 с
# запасом ~7% над максимумом"). WARN_TEXT_BUDGET_CHARS = 550 (максимум
# 513 + ~7% на правки хвостов без структурного роста, ХРАПОВИК -- не
# понижается без нового замера, D-0105 п.6(а)).
# ---------------------------------------------------------------------

WARN_TEXT_BUDGET_CHARS = 550


@pytest.mark.parametrize(
    "name,render,_verbs", _VERB_CASES, ids=[c[0] for c in _VERB_CASES]
)
def test_c4_length_within_budget(name, render, _verbs):
    text = render()
    assert len(text) <= WARN_TEXT_BUDGET_CHARS, (
        f"{name}: {len(text)} символов > бюджет {WARN_TEXT_BUDGET_CHARS} "
        f"(Р-С1, храповик) -- {text!r}"
    )


def _within_length_budget(text: str) -> bool:
    """Сам предикат бюджета -- ВЫНЕСЕН отдельно, чтобы граничные тесты
    ниже проверяли РОВНО ТУ ЖЕ логику, что test_c4_length_within_budget
    применяет к боевой батарее (не дублирующее сравнение)."""
    return len(text) <= WARN_TEXT_BUDGET_CHARS


def _synthetic_text_of_length(length: int) -> str:
    """Параметр-хелпер границы (М2-4, край спеки: "синтетикой через
    параметр-хелпер, не порчей живых констант") -- генерирует
    СИНТЕТИЧЕСКУЮ строку заданной длины, ни одна боевая константа
    реестра не трогается."""
    return "x" * length


def test_c4_length_budget_boundary_at_550_passes():
    text = _synthetic_text_of_length(WARN_TEXT_BUDGET_CHARS)
    assert len(text) == 550
    assert _within_length_budget(text) is True


def test_c4_length_budget_boundary_551_beyond_fails():
    text = _synthetic_text_of_length(WARN_TEXT_BUDGET_CHARS + 1)
    assert len(text) == 551
    assert _within_length_budget(text) is False


# ---------------------------------------------------------------------
# C-К4 (3/4): наличие префикса реестра -- literal каждого слоя реестра
# байт-в-байт в НАЧАЛЕ соответствующего рендера.
# ---------------------------------------------------------------------

_PREFIX_CASES = [
    ("OWNS_OVERLAP", _render_owns_overlap),
    ("BLIND_OWNS", lambda: owns_gate.BLIND_OWNS_WARN_MESSAGE),
    ("QUOTED_OWNS", lambda: owns_gate.QUOTED_OWNS_WARN_MESSAGE),
    ("NOTES_LEN", _render_notes_len),
    ("TIER_ECHO", lambda: _render_tier_echo("mismatch")),
    ("WITNESS_ECHO", lambda: _render_witness_echo("warn_loud")),
    ("TS_DRIFT", lambda: _render_ts_drift("future")),
    ("R6_ZERKALO", _render_r6_zerkalo),
    ("NEGATIVE_LINT", _render_negative_lint),
    ("NEGATIVE_CLAIM", _render_negative_claim),
    ("SEARCH_RETURNED_NOTHING", _render_search_returned_nothing),
]


@pytest.mark.parametrize("layer_id,render", _PREFIX_CASES, ids=[c[0] for c in _PREFIX_CASES])
def test_c4_registry_prefix_present(registry, layer_id, render):
    literal = _layer(registry, layer_id)["literal"]
    text = render()
    assert text.startswith(literal), f"{layer_id}: {text[:80]!r} does not start with {literal!r}"


def test_c4_hygiene_registry_prefix_present_in_wrapped_context(registry):
    # HYGIENE -- литерал "Командная гигиена: " -- это ОБЁРТКА decide(),
    # не сам MSG_* текст (см. докстринг журнала правки hygiene_gate_msg.py);
    # алиас "Командная гигиена (WARN, не блокирует): " проверяется прямо.
    layer = _layer(registry, "HYGIENE")
    wrapped = _render_hygiene_wrapped()
    assert any(wrapped.startswith(a) for a in layer["aliases"])


# ---------------------------------------------------------------------
# C-К4 (4/4): отсутствие перекрытия литералов -- пары ВСЕХ 18 записей
# реестра (не только шести носителей узла C -- инвариант реестра
# целиком), литерал + алиасы. Не требует импорта модулей узла A.
# ---------------------------------------------------------------------


def _all_literal_strings(registry_data) -> list:
    out = []
    for layer in registry_data["layers"]:
        out.append((layer["id"], layer["literal"]))
        for alias in layer.get("aliases") or []:
            out.append((layer["id"] + ":alias", alias))
    return out


def test_c4_no_literal_overlap_across_full_registry(registry):
    strings = _all_literal_strings(registry)
    for i, (id_a, lit_a) in enumerate(strings):
        for id_b, lit_b in strings[i + 1 :]:
            if id_a.split(":")[0] == id_b.split(":")[0]:
                continue  # тот же слой и его собственный алиас -- не перекрытие
            assert lit_a not in lit_b and lit_b not in lit_a, (
                f"{id_a} ({lit_a!r}) перекрывается с {id_b} ({lit_b!r})"
            )


# ---------------------------------------------------------------------
# C-К3 obход (D-0100): по каждому из 13 записей реестра шести носителей
# -- вердикт "разделён / разделения не требует -- почему". Машинный пин
# ЧИСЛА веток -- прозы "остальные проверены" не будет ни здесь, ни в
# отчёте (см. отчёт билдера за текстовую версию перечисления).
# ---------------------------------------------------------------------

_CK3_SPLIT_VERDICTS = {
    "OWNS_OVERLAP": 1,  # один код-путь, одно действие -- разделения не требует
    "BLIND_OWNS": 1,
    "QUOTED_OWNS": 1,
    "NOTES_LEN": 1,
    "TIER_ECHO": 2,  # mismatch/info -- уже разделены (kind-ветка)
    "WITNESS_ECHO": 3,  # warn_loud/warn_stale/warn_soft -- уже разделены
    "TS_DRIFT": 2,  # future/stale -- уже разделены
    "R6_ZERKALO": 1,
    "R3_ZERKALO": 2,  # M1 (нет входа) / M2 (фантомное основание) -- разделены
                      # по случаю самим слоем (t-609, посажен 2026-08-25 —
                      # вошёл в carrier journal_echo ПОСЛЕ снятия сиблингов C)
    "JOURNAL_ECHO_BASE": 1,  # обёртка, вне owns -- см. build_context
    "NEGATIVE_LINT": 1,
    "NEGATIVE_CLAIM": 1,
    "SEARCH_RETURNED_NOTHING": 1,
    "HYGIENE": 4,  # MSG_CD_PREFIX/MSG_REDIRECT_STDERR/MSG_PYTHON_DASH_C/MSG_CD_NON_ROOT_WARN
}


def test_c3_split_verdict_enumeration_covers_all_thirteen_layers(registry):
    node_c_carriers = {
        "tools/owns_gate.py",
        "tools/journal_echo.py",
        "tools/negative_lint.py",
        "tools/claim_control_gate.py",
        "tools/search_control_gate.py",
        "tools/hygiene_gate.py",
    }
    node_c_layer_ids = {
        layer["id"] for layer in registry["layers"] if layer["carrier"][0] in node_c_carriers
    }
    assert node_c_layer_ids == set(_CK3_SPLIT_VERDICTS.keys())
    # 14 с посадкой R3-ЗЕРКАЛО (t-609, тот же день, тот же carrier).
    assert len(node_c_layer_ids) == 14


# ---------------------------------------------------------------------
# Адверсариальная батарея (частичная, в границах сужённого witness --
# полная батарея warn_density/validate_layers снимается Lead'ом на
# посадке, поправка Lead п.2).
# ---------------------------------------------------------------------


def test_adversarial_emoji_in_dynamic_part_does_not_crash_and_keeps_static_prefix():
    # эмодзи/суррогаты в ДИНАМИЧЕСКОЙ части (declared_word) -- санитайзер
    # не должен падать, статическая часть текста (литерал + рамка) не
    # тронута.
    event = (2, "mismatch", "sonnet\U0001F600", {"claude-opus-4-8": 1})
    text = journal_echo._format_tier_line(event, ascii_only=False)
    assert text.startswith("TIER ECHO: строка 2 заявлен ярус")
    assert "сверь" in text.lower()


def test_adversarial_ascii_only_channel_sanitizes_non_ascii_dynamic_part():
    # non-UTF8 консоль Windows -- ascii_only=True ветка не должна кидать
    # исключение и обязана заменить не-ASCII в ДИНАМИКЕ на "?"; статика
    # остаётся кириллицей/ASCII как есть (санитайз статики не требуется).
    event = ("warn_loud", 2, "pytest -q café", "2026-08-25T10:00:00")
    text = journal_echo._format_witness_line(event, ascii_only=True)
    assert text.startswith("WITNESS ECHO: line 2 contradiction")
    assert "café" not in text


def test_adversarial_hygiene_both_alias_forms_alive_in_module_source():
    # HYGIENE -- слой с алиасом (спека, "Адверсариальная батарея"):
    # обе формы обёртки живы в носителе -- этот узел НЕ трогал wrapping-
    # код decide(), только MSG_*-константы; регресс-пин.
    # ПОСЛЕ ПОСАДКИ (2026-08-25): сиблинг удалён, пин держит ЖИВОЙ носитель.
    source = (TOOLS_DIR / "hygiene_gate.py").read_text(encoding="utf-8")
    assert "Командная гигиена: " in source
    assert "Командная гигиена (WARN, не блокирует): " in source


def test_adversarial_no_literal_carries_open_brace():
    # "литерал с `{` -> validate_layers даёt дефект" -- новые тексты
    # (BLIND_OWNS/QUOTED_OWNS/NEGATIVE_LINT-хвост и т.д.) не должны
    # случайно ввести "{" в СТАТИЧЕСКУЮ (не форматную f-string) часть,
    # которая попала бы в реестр как literal -- пин на уже кодированных
    # литералах реестра самих по себе (они не менялись этим узлом).
    with WARN_LAYERS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    for layer in data["layers"]:
        assert "{" not in layer["literal"], layer["id"]


def test_adversarial_tier_segment_boundary_5_vs_6_still_caps_with_new_text():
    # MAX_TIER_LINES=5/6 -- граница, унаследованная (не введена этим
    # узлом), но текст-правка _format_tier_line НЕ должна ломать
    # потолок build_tier_segment: 5 событий -> все влезли, 6 -> "+1 more".
    events5 = [(i, "info", "sonnet", {"claude-sonnet-5": 1}) for i in range(1, 6)]
    events6 = [(i, "info", "sonnet", {"claude-sonnet-5": 1}) for i in range(1, 7)]
    seg5 = journal_echo.build_tier_segment(events5, ascii_only=False)
    seg6 = journal_echo.build_tier_segment(events6, ascii_only=False)
    assert seg5.count("TIER ECHO") == 5
    assert "more" not in seg5
    assert seg6.count("TIER ECHO") == 5
    assert "+1 more" in seg6


# ---------------------------------------------------------------------
# ПОЗИЦИОННЫЙ край (спека узла C): множество входов, на которых слой
# МОЛЧИТ, ТОЖДЕСТВЕННО до/после -- прямой тест по факту непустоты, не
# по тексту. Пустой вход -- ни один текст не рендерится (правки не
# перемещают вычисление строки выше ранней проверки).
# ---------------------------------------------------------------------


def test_positional_empty_tier_events_still_silent():
    assert journal_echo.build_tier_segment([], ascii_only=False) == ""


def test_positional_empty_witness_events_still_silent():
    assert journal_echo.build_witness_segment([], ascii_only=False) == ""


def test_positional_empty_ts_drift_events_still_silent():
    assert journal_echo.build_ts_drift_segment([], ascii_only=False) == ""


def test_positional_readonly_prompt_no_owns_marker_stays_silent(tmp_path):
    # Позиционный инвариант (спека узла C): множество входов, на которых
    # слой МОЛЧИТ, тождественно до/после -- прямой тест по факту
    # непустоты, не по тексту. Read-only-промпт без owns-маркера вовсе
    # -- ни BLIND_OWNS, ни QUOTED_OWNS не рендерятся (ранний возврат
    # decide() ДО формирования текста -- правки этого узла только в
    # объявлениях констант, ни одна не встала в условную ветку).
    exit_code, result = owns_gate.decide(
        {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "builder",
                "prompt": "Прочитай файл x.py и опиши логику. DoD: явный ответ да/нет.",
            },
            "cwd": str(REPO_ROOT),
        },
        registry_path=tmp_path / "owns_registry_scratch.jsonl",
    )
    assert exit_code == 0
    assert result is None


def test_positive_control_blind_owns_still_fires_end_to_end_with_new_tail(tmp_path):
    # Позитивный контроль в паре (командная гигиена п.6): та же decide()
    # ветка, но с owns-маркером БЕЗ разбираемого пути + write-глаголом --
    # BLIND_OWNS_WARN_MESSAGE рендерится сквозь decide(), новый хвост
    # виден в реальном JSON-выводе, не только в прямом доступе к
    # константе.
    exit_code, result = owns_gate.decide(
        {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "builder",
                "prompt": "DoD: witness есть. owns объявлен. Правь файл x.py.",
            },
            "cwd": str(REPO_ROOT),
        },
        registry_path=tmp_path / "owns_registry_scratch.jsonl",
    )
    assert exit_code == 0
    assert result is not None
    ctx = result["hookSpecificOutput"]["additionalContext"]
    assert ctx == owns_gate.BLIND_OWNS_WARN_MESSAGE
