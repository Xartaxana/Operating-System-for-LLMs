"""Тесты tools/mechanism_gate.py — гейт осевого блока правила 10(б), D-0055."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

import mechanism_gate as mg

MAP_SAMPLE = """# Sibling Map
## Ось 1 — Деплои
...
## Ось 2 — Контуры
...
## Ось 6 — Внутренние оси
...
## Проверка самой карты (D-0048)
"""

# t-068 / D-0072: конфиг с Claude-привязкой (как реальный
# toolkit/delegation.config.yaml) и конфиг с не-Claude привязкой.
CONFIG_SAMPLE = """
roles:
  lead:
    subscription:
      model: claude-fable-5
    api:
      provider:
      model:
      api_key_env:
"""

CONFIG_SAMPLE_NON_CLAUDE = """
roles:
  lead:
    subscription:
      model:
    api:
      provider: groq
      model: llama-3.3-70b-versatile
      api_key_env: GROQ_API_KEY
"""

# D-0099 (2026-08-04): конфиг с Lead-привязкой на opus -- сценарий
# переезда Fable -> Opus 5.
CONFIG_SAMPLE_OPUS = """
roles:
  lead:
    subscription:
      model: claude-opus-5
    api:
      provider:
      model:
      api_key_env:
"""


def test_parse_axes_follows_the_map_not_a_constant():
    # D-0048/D-0055: число и номера осей приходят из карты при каждом
    # запуске; разрыв нумерации (2 -> 6) не ломает парсер.
    assert mg.parse_axes(MAP_SAMPLE) == [1, 2, 6]
    assert mg.parse_axes("# пусто\n") == []


def test_mechanism_paths_filters_prefixes_with_boundary():
    staged = ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
              ".claude/agents/scout.md", "gateway/metrics.py",
              "docs/RELATED_WORK.md", "logs/routing-log.jsonl"]
    assert mg.mechanism_paths(staged) == [
        "CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        ".claude/agents/scout.md"]
    # F-D (ревью critic): граница префикса — файловые префиксы матчатся точно.
    assert mg.mechanism_paths(["CLAUDE.md.bak", "DECISIONS.md.orig",
                               "gateway/metrics.py"]) == []


def test_mechanism_paths_d0065_homes_and_self_protection():
    # D-0065 (F-25): дома механизмов + самозащита цепочки в неводе.
    extra = ["ARCHITECTURE.md", "ARCHITECTURE_BOOT.md", "BOOT.md",
             "gateway/PI_HARNESS.md",
             "tools/mechanism_gate.py", ".githooks/commit-msg",
             ".claude/settings.json"]
    assert mg.mechanism_paths(extra) == extra
    # Узость сознательна (D-0055): прочие tools/ и gateway/ вне невода.
    assert mg.mechanism_paths(["tools/usage_report.py",
                               "tools/test_mechanism_gate.py",
                               "gateway/config.yaml",
                               ".claude/settings.local.json",
                               "ARCHITECTURE.md.bak"]) == []


def test_find_missing_reports_absent_axes_case_insensitive():
    text = "ось 1: покрыта — CLAUDE.md обоих деплоев\nОсь 2: н-п (денег не касается)\n"
    assert mg.find_missing(text, [1, 2, 6]) == [6]
    assert mg.find_missing(text + "ось 6: в очередь (AO3 next touch)\n", [1, 2, 6]) == []
    # Граница цифры: «ось 15:» не закрывает ось 1.
    assert mg.find_missing("ось 15: покрыта\n", [1]) == [1]


def test_prose_answer_is_not_an_answer():
    # F-19: recall-проза «оси покрыты» не проходит перечислительный формат.
    assert mg.find_missing("все оси покрыты, проверено", [1, 2]) == [1, 2]


def test_decide_skip_only_from_commit_message():
    # F-A (блокер из ревью critic): строка отказа, процитированная в
    # ДИФФЕ (текст решения), НЕ обходит гейт; действует только сообщение.
    code, reason = mg.decide(
        msg="feat: механизм X",
        block_extra="+ ... легальна строкой «оси: не-механизм (<причина>)» ...",
        staged=["CLAUDE.md"], map_text="## Ось 1 — Деплои\n")
    assert code == 1 and "1" in reason
    code, _ = mg.decide(
        msg="docs: правка опечатки\n\nоси: не-механизм (опечатка в правиле 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 — Деплои\n")
    assert code == 0


def test_decide_block_counted_from_message_and_decisions_diff_only():
    # F-B (ревью critic): посторонний staged-контент не закрывает оси —
    # decide получает дифф ТОЛЬКО DECISIONS_FULL, main так и вызывает.
    code, _ = mg.decide(
        msg="feat: механизм X\n\nось 1: покрыта — оба деплоя",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0
    code, _ = mg.decide(
        msg="feat: механизм X",
        block_extra="+ось 1: покрыта — оба деплоя (текст решения)",
        staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


def test_decide_merge_and_non_mechanism_commits_pass():
    # F-C (ревью critic): merge не блокируется — слитые коммиты уже
    # проходили гейт поодиночке.
    code, _ = mg.decide(msg="Merge branch 'x'", block_extra="",
                        staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
                        merging=True)
    assert code == 0
    code, _ = mg.decide(msg="chore: телеметрия", block_extra="",
                        staged=["gateway/metrics.py", "logs/routing-log.jsonl"],
                        map_text="## Ось 1 —\n")
    assert code == 0


def test_decide_fails_closed_without_map_or_axes():
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text=None)
    assert code == 1 and "fail-closed" in reason
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text="# карта без осей\n")
    assert code == 1 and "fail-closed" in reason


def test_explicit_skip_line_matches():
    assert mg.SKIP_RE.search("оси: не-механизм (правка опечатки в CLAUDE.md)")
    assert mg.SKIP_RE.search("Оси: не-механизм (архивная перестановка, D-0038)")
    assert not mg.SKIP_RE.search("оси покрыты не-механизмом")


# --- D-0093 (полигон Dog): якорь SKIP_RE — только ОТДЕЛЬНАЯ строка ------
# Контраст: TIER_LINE_RE уже был заякорен ^…$ MULTILINE (t-278); SKIP_RE
# был fail-open — .search() без якоря матчил инлайн-цитату синтаксиса
# отказа посреди прозы коммит-сообщения, глуша гейт целиком.


def test_skip_re_standalone_line_in_multiline_message():
    # (1) отдельная строка внутри многострочного сообщения → активен.
    msg = "feat: механизм X\n\nоси: не-механизм (причина)\n\nдоп. текст\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_standalone_line_with_space_indent():
    # (2) та же строка с отступом пробелами → активен.
    msg = "feat: механизм X\n\n   оси: не-механизм (причина с отступом)\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_inline_quote_mid_sentence_does_not_match():
    # (3) инлайн-цитата в середине предложения → НЕ активен.
    msg = ("feat: механизм X\n\nстрока «оси: не-механизм (пример)» "
           "обходила бы гейт, если бы не якорь\n")
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_line_starting_with_guillemet_does_not_match():
    # (4) строка, начинающаяся с «ёлочки» → НЕ активен (перед «оси» стоит
    # непробельный символ «, якорь ^\s* его не пропускает).
    msg = "feat: механизм X\n\n«оси: не-механизм (пример)»\n"
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_line_starting_with_straight_quote_does_not_match():
    # (5) строка, начинающаяся с прямой кавычки " → НЕ активен.
    msg = 'feat: механизм X\n\n"оси: не-механизм (пример)"\n'
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_matches_on_crlf_message():
    # (6) CRLF-сообщение: отдельная строка с \r\n-концами → активен (после
    # \n MULTILINE-якорь встаёт сразу перед «оси», без ведущего \r).
    msg = "feat: механизм X\r\n\r\nоси: не-механизм (причина)\r\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_first_line_of_message_no_leading_newline_matches():
    # (6b, критик t-288 тест-гэп) skip-строка — САМАЯ ПЕРВАЯ строка
    # сообщения целиком, БЕЗ ведущего \n (в отличие от (1)/(2)/(6) выше,
    # где skip-строке предшествует хотя бы один перевод строки) →
    # активен: MULTILINE ^ матчит и позицию 0 строки, не только позицию
    # сразу после \n.
    msg = "оси: не-механизм (причина, без ведущего текста)\n\nдоп. текст\n"
    assert mg.SKIP_RE.search(msg)


def test_decide_first_line_skip_no_leading_newline_passes():
    # (8b, критик t-288 тест-гэп) сквозной кейс через decide(): то же
    # самое сообщение (skip-строка первой, без ведущего \n) реально
    # пропускает механизменный коммит без осевого блока.
    msg = "оси: не-механизм (опечатка в правиле 3)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Ось 1 — Деплои\n")
    assert code == 0


def test_decide_inline_quote_without_axis_block_blocks():
    # (7) сквозной кейс через decide(): механизменный staged-путь,
    # сообщение с ИНЛАЙН-цитатой skip-синтаксиса и БЕЗ осевого блока →
    # гейт БЛОКИРУЕТ (код 1) — цитата не активирует skip.
    msg = ("feat: механизм X\n\nстрока «оси: не-механизм (пример)» "
           "обходила бы гейт\n")
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                             map_text="## Ось 1 — Деплои\n")
    assert code == 1 and "1" in reason


def test_decide_standalone_skip_line_passes():
    # (8) сквозной кейс: настоящая skip-строка отдельной строкой → код 0.
    msg = "docs: правка опечатки\n\nоси: не-механизм (опечатка в правиле 3)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Ось 1 — Деплои\n")
    assert code == 0


# --- t-068 / D-0072: строка tier на ветке «механизм» ---------------------

def test_resolve_lead_binding_defaults_to_fable_without_config():
    assert mg.resolve_lead_binding(None) == "fable"
    assert mg.resolve_lead_binding("roles: {}\n") == "fable"
    assert mg.resolve_lead_binding("not: yaml: [broken\n") == "fable"


def test_resolve_lead_binding_reads_subscription_model():
    assert mg.resolve_lead_binding(CONFIG_SAMPLE) == "claude-fable-5"


def test_resolve_lead_binding_falls_back_to_api_for_non_claude():
    assert (mg.resolve_lead_binding(CONFIG_SAMPLE_NON_CLAUDE)
            == "llama-3.3-70b-versatile")


def test_tier_declared_ok_exact_and_family_vs_non_claude():
    assert mg.tier_declared_ok("claude-fable-5", "claude-fable-5")
    assert mg.tier_declared_ok("fable", "claude-fable-5")
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5")
    # не-Claude привязка: семейства нет, годится только точное совпадение.
    assert mg.tier_declared_ok("llama-3.3-70b-versatile",
                               "llama-3.3-70b-versatile")
    assert not mg.tier_declared_ok("fable", "llama-3.3-70b-versatile")


def test_decide_full_missing_tier_line_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта — оба деплоя",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "tier" in reason.lower()
    assert "Lead-очередь" in reason


def test_decide_full_tier_mismatch_fails_with_distinct_text():
    # lead binding по умолчанию (нет конфига) = "fable"; sonnet не подходит.
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "не lead" in reason
    # текст отличим от текста «нет строки»
    assert "Нет строки" not in reason


def test_decide_full_tier_fable_default_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 0


def test_decide_full_tier_exact_model_id_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: claude-fable-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE)
    assert code == 0


def test_decide_full_skip_line_without_tier_passes():
    code, _ = mg.decide_full(
        msg="docs: опечатка\n\nоси: не-механизм (опечатка в правиле 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 0


def test_decide_full_merge_commit_without_tier_passes():
    code, _ = mg.decide_full(
        msg="Merge branch 'x'", block_extra="", staged=["CLAUDE.md"],
        map_text="## Ось 1 —\n", config_text=None, merging=True)
    assert code == 0


# --- t-278 п.5 (критик t-068): ВСЕ найденные tier-строки, не только первая ---


def test_find_tier_declarations_returns_all_lines_in_order():
    msg = "feat: X\n\ntier: sonnet\n\nSome other text\ntier: fable\n"
    assert mg.find_tier_declarations(msg) == ["sonnet", "fable"]


def test_find_tier_declaration_backward_compat_returns_first():
    msg = "feat: X\n\ntier: sonnet\n\ntier: fable\n"
    assert mg.find_tier_declaration(msg) == "sonnet"


def test_decide_full_first_line_garbage_second_real_still_rejects():
    # Критик t-068: старое поведение (.search() -- только первая строка)
    # либо взяло бы ТОЛЬКО мусорную первую строку (и корректно отказало
    # бы -- случайно), либо (при иной реализации "любая совпадает")
    # пропустило бы коммит по НАСТОЯЩЕЙ второй строке, спрятав мусорную/
    # спуфинг-строку. Выбранная семантика ("все должны пройти") ловит
    # ОБЕ строки и отказывает по мусорной, даже если рядом есть верная.
    msg = (
        "feat: механизм X\n\nось 1: покрыта\n\n"
        "Пример из докстринга (цитата, своя строка):\n"
        "tier: sonnet\n\n"
        "tier: fable\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "не lead" in reason
    assert "sonnet" in reason


def test_decide_full_real_first_garbage_second_still_rejects():
    # Порядок строк не важен -- проверяются ВСЕ найденные независимо от
    # позиции.
    msg = "feat: механизм X\n\nось 1: покрыта\n\ntier: fable\ntier: sonnet\n"
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "не lead" in reason


def test_decide_full_multiple_matching_tier_lines_passes():
    # Несколько механизмов в одном коммите, обе строки — настоящие и
    # совпадающие с привязкой -- проходит.
    msg = "feat: механизм X\n\nось 1: покрыта\n\ntier: fable\ntier: fable\n"
    code, _ = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 0


def test_decide_full_non_claude_lead_requires_exact_match():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: llama-3.3-70b-versatile",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 0
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 1
    assert "не lead" in reason


# --- D-0099 (2026-08-04): декларация яруса ВЫШЕ привязки легальна (П2) ---


def test_tier_declared_ok_family_above_binding_passes():
    # Привязка opus, декларация fable (голое семейство и полный model id) --
    # ранг fable (0) СТРОГО ВЫШЕ ранга opus (1) -- принимается.
    assert mg.tier_declared_ok("fable", "claude-opus-5")
    assert mg.tier_declared_ok("claude-fable-5", "claude-opus-5")


def test_tier_declared_ok_family_below_binding_fails():
    # Та же opus-привязка, декларация НИЖЕ (sonnet/haiku) -- не проходит.
    assert not mg.tier_declared_ok("sonnet", "claude-opus-5")
    assert not mg.tier_declared_ok("haiku", "claude-opus-5")


def test_tier_declared_ok_fable_binding_nothing_above_regression_pin():
    # ГРАНИЦА: привязка fable — регресс-пин "выше fable ничего нет", ранг
    # fable уже 0 (индексов меньше не существует) -- декларация opus/любая
    # другая по-прежнему не проходит новой веткой (сегодняшнее поведение).
    assert not mg.tier_declared_ok("opus", "claude-fable-5")
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5")


def test_tier_declared_ok_non_claude_binding_unaffected_by_new_branch():
    # Привязка не-Claude (fam(binding) is None) -- функция возвращает False
    # ДО новой ветки в принципе, регресс-пин.
    assert not mg.tier_declared_ok("fable", "llama-3.3-70b-versatile")


def test_tier_declared_ok_non_claude_declaration_does_not_match_higher_family():
    # ГРАНИЦА новой ветки с другой стороны: привязка opus (Claude), но
    # ДЕКЛАРАЦИЯ не-Claude (declared_fam is None) -- новая ветка не
    # матчит вовсе, fail-closed (годится только точное совпадение).
    assert not mg.tier_declared_ok("llama-3.3-70b-versatile", "claude-opus-5")


def test_decide_full_lead_binding_opus_tier_fable_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE_OPUS)
    assert code == 0


def test_decide_full_lead_binding_opus_tier_sonnet_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE_OPUS)
    assert code == 1
    assert "не lead" in reason


def test_decide_full_lead_binding_fable_tier_opus_fails():
    # Регресс-пин: привязка fable -- "выше" ничего нет, tier: opus (ниже
    # fable) по-прежнему отклонён.
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: opus",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE)
    assert code == 1
    assert "не lead" in reason


def test_decide_full_lead_binding_non_claude_tier_fable_fails():
    # Регресс-пин: не-Claude привязка -- декларация выше по рангу не
    # спасает (ветка молчит для fam(binding) is None).
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 1
    assert "не lead" in reason


# --- D-0099 п.6 (2026-08-04): онбординг-лестница конфига (build_role_ladder /
# _resolve_ladder_rank / tier_declared_ok config_text) -----------------------

CONFIG_LADDER_NON_CLAUDE = """
roles:
  critic:
    subscription:
      model: gpt-x
  lead:
    subscription:
      model: llama-3.3-70b-versatile
"""

CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE = """
roles:
  lead:
    subscription:
      model: llama-3.3-70b-versatile
  reserve:
    subscription:
      model: claude-fable-5
"""

CONFIG_LADDER_OPUS_LEAD_FABLE_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-fable-5
"""

CONFIG_LADDER_AMBIGUOUS_FAMILY = """
roles:
  critic:
    subscription:
      model: claude-critic-opus-x
  reserve:
    subscription:
      model: claude-reserve-opus-y
  lead:
    subscription:
      model: llama-3.3-70b-versatile
"""

CONFIG_LADDER_WITH_NON_COORD_ROLES = """
roles:
  scout:
    subscription:
      model: claude-haiku-3
  builder:
    subscription:
      model: claude-sonnet-5
  critic:
    subscription:
      model: claude-opus-4
  lead:
    subscription:
      model: claude-opus-5
  judge:
    subscription:
      model: claude-judge-model
  analyst:
    subscription:
      model: claude-analyst-model
  designer:
    subscription:
      model: claude-designer-model
"""


def test_build_role_ladder_fixed_order_and_ranks():
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    assert ladder == [
        (0, "claude-haiku-3"),
        (1, "claude-sonnet-5"),
        (2, "claude-opus-4"),
        (3, "claude-opus-5"),
    ]


def test_build_role_ladder_ignores_judge_and_analyst():
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    ids = [model_id for _rank, model_id in ladder]
    assert "claude-judge-model" not in ids
    assert "claude-analyst-model" not in ids


def test_build_role_ladder_ignores_designer():
    # B4.3 (пересдача, критик-блокер): designer -- стоячая функция того же
    # яруса, что critic (opus), НО НЕ координационная ступень лестницы
    # (roles.designer не в ROLE_RANKS) -- по образцу judge/analyst выше.
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    ids = [model_id for _rank, model_id in ladder]
    assert "claude-designer-model" not in ids
    assert len(ladder) == 4  # scout/builder/critic/lead only


def test_build_role_ladder_role_without_model_no_rung():
    # roles.reserve присутствует ключом, но без модели -- ступени нет.
    config = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model:
"""
    assert mg.build_role_ladder(config) == [(3, "claude-opus-5")]


def test_build_role_ladder_empty_without_config():
    assert mg.build_role_ladder(None) == []
    assert mg.build_role_ladder("") == []
    assert mg.build_role_ladder("not: yaml: [broken\n") == []


def test_tier_declared_ok_non_claude_ladder_exact_id_lead_passes():
    # ЛЕСТНИЦА не-Claude: lead=llama-3.3-70b-versatile, critic=gpt-x --
    # декларация ТОЧНЫМ id ступени lead проходит.
    assert mg.tier_declared_ok(
        "llama-3.3-70b-versatile", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE)


def test_tier_declared_ok_non_claude_ladder_lower_rung_fails():
    # Та же лестница -- декларация ступени critic (ранг НИЖЕ lead) не
    # проходит.
    assert not mg.tier_declared_ok(
        "gpt-x", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE)


def test_tier_declared_ok_reserve_exact_id_passes_at_non_claude_lead():
    # reserve=claude-fable-5 при не-Claude lead -- декларация ТОЧНЫМ id
    # ступени reserve (ранг СТРОГО ВЫШЕ lead) проходит.
    assert mg.tier_declared_ok(
        "claude-fable-5", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE)


def test_tier_declared_ok_reserve_family_match_passes_at_non_claude_lead():
    # Тот же конфиг -- декларация "fable" (голое семейство, family-матч
    # РОВНО одной ступени reserve) тоже проходит.
    assert mg.tier_declared_ok(
        "fable", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE)


def test_tier_declared_ok_real_shape_opus_lead_fable_reserve_passes():
    # Реальный вид (lead: claude-opus-5, reserve: claude-fable-5) --
    # "tier: fable" проходит (через П2-ветку И/ИЛИ лестницу -- обе
    # сосуществуют, оба пути дают True для этой конфигурации).
    assert mg.tier_declared_ok(
        "fable", "claude-opus-5", CONFIG_LADDER_OPUS_LEAD_FABLE_RESERVE)


def test_tier_declared_ok_no_reserve_tier_fable_still_passes_via_p2():
    # ГРАНИЦА: roles.reserve отсутствует -- лестница без ступени 4 (у неё
    # просто нет ранга 4 вовсе), "tier: fable" при opus-lead всё равно
    # проходит через П2-ветку (семейство строго выше привязки) -- обе
    # ветки сосуществуют, отсутствие ступени 4 не ломает П2.
    ladder = mg.build_role_ladder(CONFIG_SAMPLE_OPUS)
    assert all(rank != 4 for rank, _model in ladder)
    assert mg.tier_declared_ok("fable", "claude-opus-5", CONFIG_SAMPLE_OPUS)


def test_tier_declared_ok_ambiguous_family_match_does_not_resolve():
    # ГРАНИЦА (документированная развилка п.6): ДВЕ ступени одного
    # Claude-семейства (critic и reserve, обе "opus") -- голое семейство
    # "opus" НЕ резолвится лестницей (амбигуитет), а привязка (lead)
    # не-Claude, так что П2-ветка тоже молчит -- итог FAIL.
    assert not mg.tier_declared_ok(
        "opus", "llama-3.3-70b-versatile", CONFIG_LADDER_AMBIGUOUS_FAMILY)


def test_tier_declared_ok_no_config_regression_pin_explicit_none():
    # Регресс-пин (первая сдача, config_text=None ЯВНО, не полагаемся на
    # реальный файл): поведение как до п.6.
    assert mg.tier_declared_ok("claude-fable-5", "claude-fable-5", None)
    assert mg.tier_declared_ok("fable", "claude-fable-5", None)
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5", None)


def test_decide_full_ladder_non_claude_lead_tier_exact_id_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: llama-3.3-70b-versatile",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_NON_CLAUDE)
    assert code == 0


def test_decide_full_ladder_non_claude_lead_tier_lower_rung_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: gpt-x",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_NON_CLAUDE)
    assert code == 1
    assert "не lead" in reason


# --- B3/B4 (пересдача, критик-блокеры, 2026-08-04) --------------------------

CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-sonnet-5
"""

CONFIG_LADDER_NO_LEAD_RESERVE_OPUS = """
roles:
  reserve:
    subscription:
      model: claude-opus-5
"""

CONFIG_LADDER_DUPLICATE_MODEL_ID = """
roles:
  builder:
    subscription:
      model: claude-fable-5
  lead:
    subscription:
      model: llama-3.3-70b-versatile
  reserve:
    subscription:
      model: claude-fable-5
"""


def test_resolve_ladder_rank_nonsense_reserve_below_lead_family_does_not_resolve():
    # B3 edge (i) (критик-блокер): reserve сконфигурирован МОДЕЛЬЮ СЛАБЕЕ
    # lead (sonnet < opus по LEAD_FAMILIES) -- позиционно reserve выше
    # (ранг 4), но семейством слабее -- family-матч НЕ резолвится вовсе.
    assert mg._resolve_ladder_rank("sonnet", CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD) is None


def test_tier_declared_ok_nonsense_reserve_below_lead_tier_sonnet_fails():
    assert not mg.tier_declared_ok(
        "sonnet", "claude-opus-5", CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD)


def test_decide_full_nonsense_reserve_below_lead_tier_sonnet_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD)
    assert code == 1
    assert "не lead" in reason


def test_resolve_ladder_rank_no_lead_rung_returns_none_even_with_reserve():
    # B3 edge (ii) (критик-блокер): roles.lead ОТСУТСТВУЕТ, reserve=opus
    # сконфигурирован -- лестничный путь не резолвит НИЧЕГО (нет опорного
    # ранга lead), несмотря на то что "opus" точным id совпал бы с reserve.
    assert mg._resolve_ladder_rank("claude-opus-5", CONFIG_LADDER_NO_LEAD_RESERVE_OPUS) is None
    assert mg._resolve_ladder_rank("opus", CONFIG_LADDER_NO_LEAD_RESERVE_OPUS) is None


def test_tier_declared_ok_no_lead_reserve_opus_tier_opus_fails():
    # Регресс-пин «выше fable ничего нет» держится и С конфигом (не только
    # с config_text=None): roles.lead отсутствует -> resolve_lead_binding
    # дефолтится в "fable" (D-0072) -- ничего не бьёт fable, ни лестницей,
    # ни family-веткой.
    binding = mg.resolve_lead_binding(CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)
    assert binding == "fable"
    assert not mg.tier_declared_ok("opus", binding, CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)


def test_decide_full_no_lead_reserve_opus_tier_opus_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: opus",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)
    assert code == 1
    assert "не lead" in reason


# --- П5(a) (батч мелочей после калибровки №6, D-0081, остаток
# критик-ревью t-350): family-strength guard теперь и на пути
# ТОЧНОГО id-совпадения _resolve_ladder_rank -----------------------

CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-sonnet-5
"""

CONFIG_LADDER_EXACT_STRONGER_FAMILY_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-sonnet-5
  reserve:
    subscription:
      model: claude-opus-5
"""

CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: llama-3.3-70b-versatile
"""


def test_resolve_ladder_rank_exact_match_weaker_family_at_reserve_does_not_resolve():
    # Нонсенс-конфиг: reserve (позиционно ранг 4, ВЫШЕ lead) сконфигу-
    # рирован МОДЕЛЬЮ СЛАБЕЕ lead семейством (sonnet < opus) -- ТОЧНОЕ
    # id-совпадение с ней БОЛЬШЕ не резолвится вовсе (guard теперь и
    # на этом пути, симметрично уже существующему B3 edge (i) на
    # family-пути).
    assert mg._resolve_ladder_rank(
        "claude-sonnet-5", CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE) is None


def test_tier_declared_ok_exact_match_weaker_family_at_reserve_fails():
    assert not mg.tier_declared_ok(
        "claude-sonnet-5", "claude-opus-5", CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE)


def test_decide_full_exact_match_weaker_family_at_reserve_rejects():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: claude-sonnet-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE)
    assert code == 1
    assert "не lead" in reason


def test_resolve_ladder_rank_exact_match_stronger_family_at_reserve_still_resolves():
    # Контрольная позитивная сторона того же guard'а: кандидат СИЛЬНЕЕ
    # (не слабее) lead семейством -- guard НЕ отбрасывает, точное
    # совпадение резолвится как раньше.
    assert mg._resolve_ladder_rank(
        "claude-opus-5", CONFIG_LADDER_EXACT_STRONGER_FAMILY_AT_RESERVE) == 4


def test_resolve_ladder_rank_exact_match_non_claude_step_trusts_ladder_position():
    # Развилка (решение Lead): семейство СТУПЕНИ-КАНДИДАТА нерезолвимо
    # (не-Claude model_id) -- guard молчит, ДОВЕРИЕ ПОЗИЦИИ ЛЕСТНИЦЫ --
    # точное совпадение резолвится (ранг 4), как и до правки.
    assert mg._resolve_ladder_rank(
        "llama-3.3-70b-versatile", CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE) == 4


def test_tier_declared_ok_exact_match_non_claude_step_trusts_ladder_position_passes():
    assert mg.tier_declared_ok(
        "llama-3.3-70b-versatile", "claude-opus-5", CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE)


def test_resolve_ladder_rank_duplicate_model_id_takes_max_rank():
    # B4 (пересдача, критик-блокер): один и тот же model_id на НЕСКОЛЬКИХ
    # ступенях (builder=1 И reserve=4, оба "claude-fable-5") -- резолюция
    # берёт МАКСИМАЛЬНЫЙ ранг среди точных совпадений (4), не первый по
    # порядку лестницы (1).
    assert mg._resolve_ladder_rank(
        "claude-fable-5", CONFIG_LADDER_DUPLICATE_MODEL_ID) == 4


def test_tier_declared_ok_duplicate_model_id_passes_via_max_rank():
    assert mg.tier_declared_ok(
        "claude-fable-5", "llama-3.3-70b-versatile", CONFIG_LADDER_DUPLICATE_MODEL_ID)


def test_decide_full_duplicate_model_id_tier_fable_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: claude-fable-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=CONFIG_LADDER_DUPLICATE_MODEL_ID)
    assert code == 0


# --- F-56 (2026-08-10): самозамыкающийся тест -- невод должен покрывать
# ВСЁ, на что реально показывает живая проводка (.claude/settings.json,
# .githooks/pre-commit, .githooks/commit-msg), а не только список,
# который кто-то переписал в MECHANISM_PREFIXES вручную. Тест читает
# ЖИВЫЕ файлы репозитория (не копии, не фикстуры) -- расхождение между
# проводкой и неводом есть РЕАЛЬНЫЙ дрейф, который должен уронить тест,
# а не тихо пройти мимо (класс F-56: тишина неотличима от покрытия).

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
LIVE_GITHOOKS_DIR = REPO_ROOT / ".githooks"

# tools/<...>.py -- одинаково матчит forward- и backslash-форму пути
# (T4: адверсариальная батарея по слэшам), останавливается на первом
# небуквенном разделителе (пробел/кавычка) -- не жуёт хвост CLI-аргументов.
_TOOL_CMD_RE = re.compile(r"tools[/\\][A-Za-z0-9_.\\/-]+\.py")


def _load_settings(path):
    # Отсутствие/битость живого файла -- НЕ повод скипнуть проверку
    # (см. докстринг блока выше): assert/исключение роняют тест громко.
    assert path.exists(), (
        f"живой {path} не найден -- самозамыкающийся тест обязан упасть "
        "громко, а не молчать (F-56: тишина неотличима от покрытия)"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(path):
    assert path.exists(), (
        f"живой {path} не найден -- самозамыкающийся тест обязан упасть "
        "громко, а не молчать (F-56: тишина неотличима от покрытия)"
    )
    return path.read_text(encoding="utf-8")


def _iter_hook_commands(settings_data):
    """Каждая command-строка из КАЖДОЙ группы КАЖДОГО события hooks --
    терпимо к пустому массиву на любом уровне (T4: «хук-массив пустой»)
    и к отсутствующим ключам (settings_data.get с дефолтами)."""
    hooks = settings_data.get("hooks", {}) or {}
    for _event, groups in hooks.items():
        for group in groups or []:
            for hook in group.get("hooks", []) or []:
                if hook.get("type") == "command" and "command" in hook:
                    yield hook["command"]


def _tool_paths_in_text(text):
    """Каждое вхождение `tools/<name>.py` в *text* (команда хука или
    целиком содержимое .githooks/*-скрипта), backslash нормализован
    на forward slash перед сверкой с MECHANISM_PREFIXES."""
    return [m.group(0).replace("\\", "/") for m in _TOOL_CMD_RE.finditer(text)]


def _uncovered_tool_paths(texts):
    uncovered = []
    for text in texts:
        for tool_path in _tool_paths_in_text(text):
            if not any(mg._matches(tool_path, pref) for pref in mg.MECHANISM_PREFIXES):
                uncovered.append(tool_path)
    return uncovered


def test_every_live_settings_hook_command_is_covered_by_mechanism_prefixes():
    data = _load_settings(LIVE_SETTINGS_PATH)
    commands = list(_iter_hook_commands(data))
    assert commands, ("живой .claude/settings.json не содержит ни одной "
                       "hook-команды -- пусто подозрительно, не считается покрытием")
    uncovered = _uncovered_tool_paths(commands)
    assert not uncovered, (
        f"hook-команды .claude/settings.json вне невода MECHANISM_PREFIXES: "
        f"{sorted(set(uncovered))}")


def test_every_githooks_script_reference_is_covered_by_mechanism_prefixes():
    pre_commit_text = _load_text(LIVE_GITHOOKS_DIR / "pre-commit")
    commit_msg_text = _load_text(LIVE_GITHOOKS_DIR / "commit-msg")
    referenced = _tool_paths_in_text(pre_commit_text) + _tool_paths_in_text(commit_msg_text)
    assert referenced, ("ни .githooks/pre-commit, ни .githooks/commit-msg не "
                         "ссылаются ни на один tools/*.py -- пусто подозрительно")
    uncovered = _uncovered_tool_paths([pre_commit_text, commit_msg_text])
    assert not uncovered, (
        f"скрипты, вызываемые из .githooks/, вне невода MECHANISM_PREFIXES: "
        f"{sorted(set(uncovered))}")


# --- t-382 (2026-08-10): ТРАНЗИТИВНОЕ импорт-замыкание живой проводки ----
# Прямых hook-команд/.githooks-скриптов недостаточно (см. критик-пробой):
# tools/journal_echo.py импортирует tier_echo (не hook-команда сама по
# себе), tools/session_context.py импортирует preflight_quota -- отказ
# ЛЮБОГО из них меняет, что обязано случиться, тем же критерием F-56, но
# прямая проверка команд их не видит. Этот блок собирает AST-импорты
# tools/*-модулей РЕКУРСИВНО от каждого живого стартового скрипта и
# утверждает: каждый достигнутый модуль покрыт MECHANISM_PREFIXES.

TOOLS_DIR = REPO_ROOT / "tools"


def _tools_module_names(tools_dir=TOOLS_DIR):
    """Множество имён модулей (без .py), реально существующих файлами
    в *tools_dir* -- граница резолюции: импорт, чьё имя НЕ входит сюда,
    не tools/-модуль (стандартная библиотека, gateway/, что угодно ещё)
    и в замыкание не попадает (T4 «импорт вне tools/ — не считается»)."""
    return {p.stem for p in tools_dir.glob("*.py")}


def _ast_tool_imports(source_text, tools_module_names):
    """Реальные (AST, не строковый греп) `import X` / `from X import
    ...` верхнего уровня в *source_text*, X резолвится ТОЛЬКО против
    *tools_module_names* -- импорт стандартной библиотеки/gateway/etc.
    просто не входит в это множество и молча исключается (не ошибка).
    Относительный импорт (`from . import X`, node.level > 0) не
    резолвится этим же путём -- отдельно НЕ раскрывается этой функцией
    (в этом репозитории relative-импорты между tools/*.py не приняты
    стилистически; документированное сужение, не угаданное молчком).
    ast.parse() поднимает SyntaxError на битом синтаксисе -- НЕ
    перехватывается здесь: вызывающая сторона решает, падать громко или
    нет (T4 «битый синтаксис файла -- тест падает громко, не скипается»)."""
    tree = ast.parse(source_text)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in tools_module_names:
                    found.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top in tools_module_names:
                    found.add(top)
    return found


def _transitive_tool_module_closure(start_modules, tools_module_names, tools_dir=TOOLS_DIR):
    """BFS-замыкание tools/*-модулей, достижимых РЕАЛЬНЫМ импортом от
    *start_modules* (голые имена модулей, без .py) -- терминирует на
    цикле через множество `seen` (T4 «циклический импорт — не
    зацикливается»): модуль добавляется в seen ДО чтения его исходника,
    так что повторная встреча с уже виденным именем (в т.ч. по кругу)
    просто не порождает новую работу. Модуль без файла на диске
    молча пропускается (best-effort, та же осанка, что у остальных
    читателей проводки этого репо, напр. tools/enforcement_probe.py)."""
    seen = set()
    frontier = list(start_modules)
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        path = tools_dir / f"{name}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for imported in _ast_tool_imports(text, tools_module_names):
            if imported not in seen:
                frontier.append(imported)
    return seen


def _live_wiring_start_tool_paths():
    """Каждый tools/*.py, названный НАПРЯМУЮ живой проводкой -- та же
    команда/скрипт-множина, что уже проверяют прямые T3-тесты выше."""
    settings_data = _load_settings(LIVE_SETTINGS_PATH)
    commands = list(_iter_hook_commands(settings_data))
    pre_commit_text = _load_text(LIVE_GITHOOKS_DIR / "pre-commit")
    commit_msg_text = _load_text(LIVE_GITHOOKS_DIR / "commit-msg")
    paths = set()
    for command in commands:
        paths |= set(_tool_paths_in_text(command))
    paths |= set(_tool_paths_in_text(pre_commit_text))
    paths |= set(_tool_paths_in_text(commit_msg_text))
    return paths


def test_transitive_import_closure_of_live_wiring_is_covered_by_mechanism_prefixes():
    start_paths = _live_wiring_start_tool_paths()
    assert start_paths, "живая проводка не назвала ни одного стартового tools/*.py"
    start_modules = {Path(p).stem for p in start_paths}
    tools_module_names = _tools_module_names()
    closure = _transitive_tool_module_closure(start_modules, tools_module_names)
    reached_paths = sorted(f"tools/{m}.py" for m in closure)
    uncovered = [p for p in reached_paths
                 if not any(mg._matches(p, pref) for pref in mg.MECHANISM_PREFIXES)]
    assert not uncovered, (
        "транзитивное импорт-замыкание живой проводки достигает модулей вне "
        f"невода MECHANISM_PREFIXES: {uncovered}\nполное замыкание: {reached_paths}")


# --- T4 (транзитивная ось): адверсариальная батарея на закрытие замыкания -


def test_ast_tool_imports_ignores_import_outside_tools():
    src = "import json\nimport os.path\nfrom pathlib import Path\n"
    assert _ast_tool_imports(src, {"tier_echo", "preflight_quota"}) == set()


def test_ast_tool_imports_finds_plain_and_from_import_forms():
    src = "import tier_echo\nfrom preflight_quota import load_config\n"
    names = {"tier_echo", "preflight_quota", "other_mod"}
    assert _ast_tool_imports(src, names) == {"tier_echo", "preflight_quota"}


def test_ast_tool_imports_ignores_relative_import():
    # Документированное сужение (см. докстринг _ast_tool_imports) --
    # relative-импорт не резолвится этим путём, не считается достижением.
    src = "from . import tier_echo\n"
    assert _ast_tool_imports(src, {"tier_echo"}) == set()


def test_ast_tool_imports_broken_syntax_raises_not_silently_skipped():
    # T4: «битый синтаксис файла — тест падает громко, не скипается».
    with pytest.raises(SyntaxError):
        _ast_tool_imports("def broken(:\n", {"tier_echo"})


def test_transitive_closure_terminates_on_circular_import(tmp_path):
    # T4: «циклический импорт — не зацикливается». Если бы алгоритм
    # зациклился, этот тест не завершился бы (обычным pytest-таймаутом
    # окружения) -- само его завершение с верным результатом ЕСТЬ
    # доказательство обрыва цикла, не только итоговое множество.
    (tmp_path / "mod_a.py").write_text("import mod_b\n", encoding="utf-8")
    (tmp_path / "mod_b.py").write_text("import mod_a\n", encoding="utf-8")
    names = {"mod_a", "mod_b"}
    closure = _transitive_tool_module_closure({"mod_a"}, names, tools_dir=tmp_path)
    assert closure == {"mod_a", "mod_b"}


def test_transitive_closure_missing_module_file_skipped_not_raising(tmp_path):
    closure = _transitive_tool_module_closure(
        {"does_not_exist_mod"}, {"does_not_exist_mod"}, tools_dir=tmp_path)
    assert closure == {"does_not_exist_mod"}


def test_transitive_closure_self_import_does_not_loop(tmp_path):
    # Вырожденный цикл длины 1 (модуль импортирует сам себя) -- тот же
    # seen-барьер обязан оборвать и эту форму.
    (tmp_path / "mod_self.py").write_text("import mod_self\n", encoding="utf-8")
    closure = _transitive_tool_module_closure(
        {"mod_self"}, {"mod_self"}, tools_dir=tmp_path)
    assert closure == {"mod_self"}


# --- T4: адверсариальная батарея на парсер самозамыкающегося теста -------


def test_tool_cmd_re_command_form_with_extra_cli_arguments():
    cmd = "python tools/hygiene_gate.py --strict --config=foo.yaml"
    assert _tool_paths_in_text(cmd) == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_forward_slash_path():
    assert _tool_paths_in_text("python tools/hygiene_gate.py") == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_backslash_path_normalised_to_forward_slash():
    assert _tool_paths_in_text("python tools\\hygiene_gate.py") == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_quoted_arg_after_path_does_not_leak_into_match():
    # .githooks/commit-msg форма: `python tools/mechanism_gate.py "$1"`.
    cmd = 'python tools/mechanism_gate.py "$1"'
    assert _tool_paths_in_text(cmd) == ["tools/mechanism_gate.py"]


def test_iter_hook_commands_tolerates_empty_hooks_array():
    # T4: «хук-массив пустой» -- на уровне группы и на уровне события.
    data = {"hooks": {"PreToolUse": [{"matcher": "X", "hooks": []}], "Stop": []}}
    assert list(_iter_hook_commands(data)) == []


def test_iter_hook_commands_tolerates_missing_hooks_key_entirely():
    assert list(_iter_hook_commands({})) == []


def test_uncovered_tool_paths_catches_drift_of_nonexistent_referenced_script():
    # T4: «несуществующий скрипт в settings — тест обязан упасть». Здесь
    # проверяется САМ детектор на синтетическом входе (не живой файл) --
    # он обязан НАЙТИ путь, которого нет в MECHANISM_PREFIXES, а не
    # молча проглотить дрейф проводки.
    drifted = "python tools/definitely_not_wired_anywhere_xyz.py --flag"
    uncovered = _uncovered_tool_paths([drifted])
    assert uncovered == ["tools/definitely_not_wired_anywhere_xyz.py"]


def test_uncovered_tool_paths_empty_for_a_fully_covered_command_set():
    # Граница напротив: набор команд, целиком лежащих в неводе -> пусто.
    covered = ["python tools/main_gate.py", "python tools/journal_validator.py"]
    assert _uncovered_tool_paths(covered) == []


# --- T3: settings.json/.githooks отсутствуют или биты -> тест ПАДАЕТ, а
# не скипается (проверяется на синтетических путях, живые файлы этой
# батареей не портятся -- п.10 гигиены, порча копий/синтетики, не боевых).


def test_load_settings_missing_file_fails_loudly_not_skipped(tmp_path):
    missing = tmp_path / "settings.json"
    with pytest.raises(AssertionError):
        _load_settings(missing)


def test_load_settings_broken_json_fails_loudly_not_skipped(tmp_path):
    broken = tmp_path / "settings.json"
    broken.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _load_settings(broken)


def test_load_text_missing_githook_file_fails_loudly_not_skipped(tmp_path):
    missing = tmp_path / "pre-commit"
    with pytest.raises(AssertionError):
        _load_text(missing)
