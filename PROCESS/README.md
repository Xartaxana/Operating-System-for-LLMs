# Engineering Process

This directory contains the engineering protocols that define how the project evolves.

The project must not depend on any individual LLM remembering the workflow.

The repository stores both project knowledge and engineering processes.

## Protocols

- PRE_COMMIT_PROTOCOL.md
- PATCH_PROTOCOL.md
- SESSION_PROTOCOL.md
- DOCUMENTATION_PROTOCOL.md
- BOOT_REPORT_PROTOCOL.md
- ZERO_CONTEXT_PROTOCOL.md
- JUDGE_CALIBRATION_PROTOCOL.md
- WEEKLY_CALIBRATION_PROTOCOL.md — еженедельная калибровка (D-0047)

## Exams (tier entrance/regression sets)

- CRITIC_EXAM.md — экзамен критика (D-0071)
- SCOUT_GOLDEN_SET.md — golden set разведки (D-0057)
- LEAD_RANKING_EXAM.md — ранжирование Lead
- DEPLOYMENT_ECONOMY_EXAM.md — экономика деплоя

До 2026-08-16 ни один из этих файлов не был перечислен здесь —
навигационный пробел против D-0007, закрыт тем же ходом, что и правило
формы поставки ниже.

### Форма поставки экзамена в кит — правило (решение Lead 2026-08-16)

Асимметрия существовала и не была записана как решение: LEAD_RANKING и
DEPLOYMENT_ECONOMY едут в кит СОДЕРЖИМЫМ, critic и scout — ГЕНЕРАТОРАМИ
(`toolkit/.claude/skills/critic-exam-gen`, `scout-exam-gen`). Правило,
которое эту асимметрию объясняет и делает воспроизводимой:

**Форма поставки следует ЗАВИСИМОСТИ НАБОРА ОТ МАТЕРИАЛА.**
- Набор, чьи задания прибиты к НАШЕМУ дереву (посеянные дефекты в
  наших файлах, золотые вопросы про наш репозиторий, реальный
  канонический счёт тестов), едет ГЕНЕРАТОРОМ. Отгруженный
  содержимым, у чужого хоста он зелен по построению и не измеряет
  ничего — то есть поставка выглядит состоявшейся, а проверки нет.
- Набор, чьи задания САМОДОСТАТОЧНЫ (суждения о лестнице ярусов,
  сценарии экономики деплоя — синтетика, не привязанная к дереву),
  едет СОДЕРЖИМЫМ: генератор здесь ничего не добавил бы.

Критерий проверяется одним вопросом к набору: «если отгрузить его как
есть чужому хосту — он останется зелёным независимо от того, что у
хоста внутри?» Да — значит нужен генератор.

ОТКРЫТО и правилом НЕ закрывается: генераторы не имеют ветки пустого
проекта, а фолбэка не существует (развилка операторская, разбор —
docs/task_reports/2026-08-16_boot-diet-extractions.md §3). Правило
говорит, КАКОЙ формой везти набор; оно не говорит, что делать, когда
материала у хоста нет вовсе.
