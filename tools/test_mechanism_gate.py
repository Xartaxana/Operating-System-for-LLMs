"""Тесты tools/mechanism_gate.py — гейт осевого блока правила 10(б), D-0055."""
from __future__ import annotations

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
