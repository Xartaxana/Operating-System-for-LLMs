# DAG: приёмка входящего от Dog 07-29 (синк 1 → наша сторона)

Задача-граф (≥5 событий журнала). Вход: коммит 2a75923 — механизм
«корреляция отрицательных утверждений» + пять предложений синка,
переданы Dog по D-0082 в наш CURRENT_CONTEXT; приёмка наша, Dog в
наше дерево ничего не ставил. Источники Dog:
`D:\Dog\tools\claim_control_gate.py`, `D:\Dog\tools\search_control_gate.py`,
`D:\Dog\docs\OUTBOUND_TO_KIT.md` (их сверка — по нашему HEAD 8e55b74;
свежесть закрыта t-337 по живому дереву).

## Вердикты приёмки (Lead, 2026-07-29)

Все 5 несущих утверждений Dog о нашем дереве ПОДТВЕРЖДЕНЫ
(t-337 + спот-чек лида по git-индексу + второй проход лида по обоим
файлам механизма, обязанность D-0066/D-0046).

| # | Предложение Dog | Вердикт | Куда |
|---|---|---|---|
| M | Механизм корреляции (половины A+B) | ADOPT, warn-first обкатка (класс negative_lint/owns_gate) | N1 порт |
| 1 | Правило 7 + enforcement_probe | ADOPT — наш wiring_check.py существует (их caveat снят) | N1, fail-closed → критик N2 |
| 2 | Регистр SKILL.md по git-индексу | ADOPT — в wiring_check (SessionStart-строка) | N1 |
| 3 | Скраб heredoc-тела коммит-сообщения | ADOPT — COMMIT_HEREDOC_RE в hygiene_gate | N1 |
| 4 | Empty-search гейт (дополнение к negative_lint) | ADOPT — входит в половину A механизма M | N1 |
| 5 | Правило об утверждениях о среде | СНЯТО ИМИ — подтверждено (CLAUDE.md п.6, строки 403–417) | — |
| 6 | Контурная разметка канонических команд | ПРИНЯТО КАК НАХОДКА — фикс в кит-CLAUDE.md, мораторий D-0074 | порт-очередь минора |
| 7 | Скоупинг условий детекторов | СНЯТО ИМИ (конвергентная находка) — заметка в руководство детекторов кита | порт-очередь минора (заметка) |

Встречное направление (Dog берёт наш negative_lint) — их носитель, у
нас действий нет.

## Узлы

- **N0 — верификация входящего** — DONE. t-337 (scout, haiku,
  accepted by fable) + спот-чек индекса + второй проход лида по двум
  файлам Dog. Read-only.
- **N1 — билдер-батч порта/правок** — t-338, builder (sonnet), DONE
  (принят basis critic 15:51; один respec-цикл по части D — spec-дефект
  диспетчера, чек-23 кейс №5; доработки F1–F9 по вердикту t-339
  исполнены; хвост: t-340 — FP Grep-классификации, вскрыт живой
  обкаткой Lead-сессии, фикс тем же воркером). WRITING node, owns
  (АБСОЛЮТНЫЕ):
  `D:\Improving_AI\Operating-System-for-LLMs\tools\search_control_gate_next.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\claim_control_gate_next.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\test_search_control_gate.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\test_claim_control_gate.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\enforcement_probe_next.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\test_enforcement_probe.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\hygiene_gate.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\test_hygiene_gate.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\wiring_check.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\tools\test_wiring_check.py`,
  `D:\Improving_AI\Operating-System-for-LLMs\.gitignore`.
  Хук-файлы и блокирующая проба — под sibling-именами `_next`
  (D-0069): на путь ставит Lead при приёмке.
- **N2 — критик батча** — t-339, critic (opus), DONE (fit_with_fixes,
  0 блокеров, 9 находок с живыми репродукциями; принят 15:19).
- **N3 — проводка и коммиты (Lead)** — DONE 07-29: _next перенесены
  на боевые имена (импорт-ссылки обновлены, 259 passed после
  переноса), хуки зарегистрированы (PreToolUse Edit|Write →
  claim_control_gate; PostToolUse Bash|PowerShell|Grep|Glob|Read →
  search_control_gate), строка пробы в `.githooks/pre-commit`,
  casing-канал проведён в session_context.wiring_lines() (lazy
  import, fail-open), liveness-пробы D-0093 исполнены (P1–P4 +
  probe: невалидный hooksPath отвергнут, откат подтверждён);
  SIBLING_MAP: ось 1 обновлена (третий wiring-модуль семейства),
  ось 11 заведена (синк-пары Dog↔штаб); RULE_COVERAGE: строки
  корреляционной пары и enforcement_probe. Коммиты — этой сессией.
- **N4 — политика и очереди (Lead)** — DONE 07-29: входящее
  архивировано (task_reports/2026-07-29_dog-incoming-closure.md),
  CURRENT_CONTEXT сжат до указателя; порт-очередь минора += пункты
  (6)–(10); очередь передачи Dog заведена (D-0082, безопасное
  касание); пункт AO3 расширен (casing + probe, негативы сверены
  грепами с контролями); чек-23 кейс t-338 — пятым в окно №5;
  обкатка: owns_gate находка №1, корреляционная пара находки №1
  (закрыта t-340) и №2 (D4b-резидуал, записан).

Порядок: N0 → N1 → N2 → N3 → N4. Статус узла движется тем же ходом,
что его событие журнала.
