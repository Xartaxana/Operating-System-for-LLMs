"""Журнальный валидатор (t-031, D-0052/D-0053/D-0058) -- pre-commit-гейт
для logs/routing-log.jsonl: ловит кодом ровно те два прецедента, что уже
случались вживую -- дубль task_id (t-029, повторная выдача без
перечитывания хвоста) и F-29 (события с ts, написанным из повествования,
«в будущем»). Стиль вызова/структура повторяют tools/mechanism_gate.py
(D-0043, ось 1: тот же дом enforcement-цепочки): чистая decide(),
тестируемая без git, main() -- тонкая git-обвязка вокруг неё.

Область: ТОЛЬКО staged-версия logs/routing-log.jsonl против HEAD-версии
(git show :logs/... vs HEAD:logs/...). Файл не staged -> main() молча
возвращает 0 (гейт не пишет вообще ничего). Только детерминированно
решаемое -- присутствие/форма/типизированные поля; смысл notes НЕ
парсится (D-0063).

Проверки (нумерация -- как в спеке t-031 / CLAUDE.md «Журнал
маршрутизации»):
 1. Append-only: staged обязана начинаться с HEAD как префикс.
 2. Каждая НОВАЯ строка -- валидный JSON-объект в одну строку с полями
    ts/event/agent/category/notes (notes непустая).
 3. event из ENUM.
 4. model обязателен для delegated/escalated/accepted/rejected.
 5. task_id обязателен для delegated/accepted/rejected/escalated/
    defect_found, формат t-NNN (3+ цифр).
 5b. Каждая НОВАЯ строка delegated несёт типизированное поле worker_ref --
    непустая строка (D-0076: хэндл, по которому следующая сессия находит
    воркера/результат; ловит фантомный delegated без запуска воркера --
    родня F-29). Только присутствие/тип/непустота; смысл хэндла судит
    приёмка. escalated полем не нагружается.
 6. rejected: attempt -- целое >=1; failure_class из ENUM.
 7. accepted с agent=builder: witness непустая строка.
 8. defect_found: ref непустой.
 9. Новизна/ссылочность task_id (ИСПРАВЛЕНО Lead-поправкой после живого
    прецедента -- «строго max+1» запрещал бы легальный critic-вход
    приёмки и ретрай после rejected). Для НОВОГО delegated:
    а) task_id == max(все t-NNN в файле до этой строки)+1 -- легально
       всегда (новая задача);
    б) task_id уже существует в файле И задача ОТКРЫТА (нет accepted
       с этим task_id выше по файлу) И agent новой строки отличается
       от agent ВСЕХ предыдущих delegated этого task_id -- легально
       (continuation-диспатч другого яруса, напр. critic-вход приёмки);
    в) task_id существует, задача открыта, agent совпадает с одним из
       предыдущих delegated -- легально ТОЛЬКО с полем attempt (целое
       >=2) И ОДНИМ ИЗ (i)/(ii) ниже (2026-08-10, дыра B3 -- порт
       AO3 AT-BUG-034, независимая сверка AO3 подтвердила: старая форма
       "retry_ok = valid_attempt and task_id in rejected_tasks"
       легализовала повторный delegated ЛЮБОГО agent по ЛЮБОМУ rejected
       на задаче -- ревьюер (напр. critic) мог войти второй раз на
       ЧУЖОЙ rejected (исполнителя) БЕЗ того, чтобы исполнитель что-то
       переделал -- см. также правило 11 модульного докстринга и
       тесты test_b3_* в tools/test_journal_validator.py):
       (i) SELF -- выше по файлу существует rejected С ЭТИМ ЖЕ agent
          (rejected.agent -- исполнитель, чей результат отклонён, R6) на
          этом task_id -- легализует собственный ретрай БЕЗ
          дополнительных условий (форма "как раньше", сужена ровно до
          "своего" rejected -- self-retry не требует никакого сигнала
          между rejected и повторным delegated);
       (ii) FOREIGN -- на task_id есть rejected, но НИ ОДИН не несёт
          agent, совпадающий со входящим ("чужой" rejected) -- легализует
          вход ТОЛЬКО если СТРОГО ПОСЛЕ ПОСЛЕДНЕГО delegated ИМЕННО
          ЭТОГО agent на этом task_id (не где-либо в истории вообще --
          сигнал из БОЛЕЕ РАННЕГО раунда протух и следующий раунд не
          легализует) появился хотя бы один сигнал новой версии объекта
          ревью:
            (1) новый delegated ДРУГОГО agent на этом task_id;
            (2) новый rejected с agent=lead на этом task_id (Lead-правка
               без своего delegated -- сам факт правки и есть сигнал);
            (3) новый escalated ДРУГОГО agent на этом task_id (2026-08-10,
               Ф5, критик-проба H2 пересдачи t-383: escalated ТОГО ЖЕ
               agent, что входит повторно, -- самолегализация петлёй,
               НЕ считается, симметрично сигналу (1); у AO3 сигнал
               завязан на эскалацию к конкретной модели полного Lead,
               здесь адаптирован на ФАКТ события escalated ДРУГОГО agent
               под тем же task_id, без привязки к ярусу/модели --
               delegation.config.yaml знает только ярусы, не модели
               внутри яруса).
          Нет ни (i), ни валидного (ii)-сигнала -> FAIL (см. (г)).
    в2) (2026-07-15, замена умершего воркера) ТОТ ЖЕ случай (agent
       совпадает, задача открыта, rejected НЕ обязателен, attempt НЕ
       растёт -- это не ретрай правила 6) -- легально, если notes
       новой строки содержат literal-подстроку "replaces_worker:" с
       непустым хэндлом СРАЗУ за ней (первый non-whitespace токен), И
       этот хэндл БУКВАЛЬНО совпадает с worker_ref какой-то предыдущей
       delegated-строки ЭТОГО ЖЕ task_id (любого agent). Защита от
       фиктивной замены: хэндл, не встречающийся ни в одном предыдущем
       delegated этого task_id, -- FAIL (см. extract_replaces_worker).
    г) всё остальное -- FAIL (дубль-паттерн t-029: тот же agent, без
       attempt, без легального (i)/(ii) выше, без валидного
       replaces_worker; и delegated на ЗАКРЫТУЮ задачу -- reopen
       запрещён, коллизия = две задачи, D-0060).
       Кросс-репо примечание (M4, docs/tasks/2026-08-25_wave2-misc-
       spec.md, docs/task_reports/2026-08-16_boot-diet-
       extractions.md:94-119/339-344): у AO3-твина (их коммиты
       441d322/6f97508) повторный delegated несёт ТРЕТЬЕ легальное
       основание -- маркер `reopen:` в notes -- и их журнал легально
       содержит такие строки. Мы этот путь НЕ принимаем: D-0060
       (reopen запрещён) остаётся ядром ЭТОГО валидатора и правила 9г
       ровно как выше -- строка с `reopen:` без (i)/(ii)/replaces_worker
       здесь всё равно FAIL. Факт зафиксирован ТОЛЬКО как ориентир для
       СКРИПТА, кросс-читающего ИХ logs/routing-log.jsonl (там их форму
       нужно allowlist'ить отдельно, не здесь) -- это правило поведения
       не меняет и такого скрипта не заводит.
    Для нового accepted/rejected/escalated/defect_found -- ссылается на
    task_id, уже встреченный выше в файле (HEAD или ранее в этом же
    коммите); без изменений.
10. ts новых строк монотонны относительно последней строки HEAD и
    между собой; не позже now+10 минут (F-29). Нижней границы нет.
11. Матрица D-0058 (только для НОВЫХ строк, только для accepted --
    rejected несёт "by" без дальнейшей проверки, буквальное чтение
    спеки). Для agent=lead матрица не применяется -- "by" достаточно
    присутствия. Для agent из {scout,builder,critic,designer}: (batch B7,
    2026-07-24 -- членство "basis in BASIS_VALUES" заменено на
    легальность ПО ПАРЕ (by, agent), после живой утечки AO3 07-24: два
    Sonnet-координатора приняли Sonnet-класс (builder) результат через
    basis=queued-to-lead -- членство пропускало basis без проверки,
    предписывает ли матрица очередь именно ЭТОЙ паре). ПРЕДШЕСТВУЕТ
    веткам (а)-(е) (t-323, порт AO3-фикса 30e79c8, 2026-07-28):
    энум-проверка "by ∈ TIER_ORDER вообще" -- при неизвестном by FAIL
    БЕЗУСЛОВНО, ДО ветки judge включительно -- by-независимость judge
    (правка t-276, ветка б ниже) действует только НА ЛЕГАЛЬНЫХ ярусных
    словах, basis никакого рода не легализует приёмку от неизвестного
    принимающего:

    а) ok_tier -- tier(by) > tier(agent) (haiku<sonnet<opus<fable по
       agent: scout=haiku, builder=sonnet, critic=opus, designer=opus
       (2026-07-30, designer-функция привязана к opus, тот же ярус, что
       critic, .claude/agents/designer.md)) -- легально
       ПРИ ЛЮБОМ basis (или без него).
    а2) (2026-08-04, D-0099) LEAD-ПРИВЯЗКА принимает финально БЕЗ basis:
       если привязка roles.lead (delegation.config.yaml, читается через
       mechanism_gate.resolve_lead_binding()) разрешима в Claude-семейство
       (mechanism_gate.lead_family(binding) is not None), И by ЛИТЕРАЛЬНО
       равен этому семейству, И tier(by) >= tier(agent) (нестрого -- РАВНЫЙ
       ярус тоже легален, в отличие от ok_tier выше) -- легально ПРИ ЛЮБОМ
       basis (или без него). Мотив: D-0099 -- полный Lead определяется
       ПРИВЯЗКОЙ, не именем "fable"; вердикт рождается в независимом
       контексте (отдельная сессия/subagent на ярусе привязки) --
       независимость контекста заменяет строгое численное превосходство
       модели при равном ярусе (напр. Lead привязан к opus -- opus-сессия
       принимает critic/designer, оба тоже opus, без критик-входа/очереди).
       Проверяется ДО ok_tier (порядок не меняет исход там, где обе ветки
       совпадают -- см. mechanism_gate.CONFIG_PATH/резолюцию ниже) --
       fable-привязка эквивалентна сегодняшнему (ok_tier уже покрывает её
       целиком), не-Claude привязка (family None) не активирует эту ветку
       вовсе (годится только сегодняшняя семантика).
    б) basis=="judge" -- легально ТОЛЬКО когда СОБСТВЕННОЕ поле
       "category" этой же строки ∈ {"recon", "implementation"}
       (лист-классы R13/D-0087, CLAUDE.md «Leaf routing»: "Judge
       acceptance is legitimate ONLY for leaf-class dispatches (recon,
       or implementation to a written spec)"); правка t-276 сохранена
       без изменений. ПРОВЕРЯЕТСЯ ПЕРВЫМ, независимо от tier(by) --
       калиброванный судья не координатор яруса, его легальность не
       завязана на ok_tier/floor ниже.
    в) FLOOR "по by ниже sonnet, координация не предусмотрена": если
       tier(by) известен (by ЛИТЕРАЛЬНО "haiku") И ok_tier не выполнен
       И basis не "judge" -- FAIL БЕЗУСЛОВНО, никакой basis не спасает
       (CLAUDE.md «Role ≠ tier» матрица: "below Sonnet | no
       coordination is provided for | --"). Развилка (документируется
       намеренно, не решена молча): буква ядра ("OR the decision
       carries a higher tier's input (a critic verdict)") читалась бы
       так, что basis="critic" спасает ЛЮБОЙ by, включая haiku -- но
       строка матрицы для "below Sonnet" не содержит исключения для
       "critic verdict" и говорит "no coordination is provided for"
       безусловно; сессия-haiku в принципе не функционирует как
       координатор в этой структуре, поэтому floor берёт верх НАД
       общим "carries higher tier's input" для basis="critic"/
       "queued-to-lead" (но НЕ для basis="judge" -- отдельный, не
       координаторский, путь приёмки, см. б). Выбор закреплён тестом
       test_matrix_haiku_by_critic_basis_below_sonnet_floor_fails.
    г) basis=="critic" -- легален ТОЛЬКО когда ярус критика (opus,
       фиксированный) СТРОГО выше яруса agent, т.е. agent -- класса
       scout/builder: критик-вход поверх собственного класса критика
       (agent=critic) смысла не имеет и НЕ легален.
    д) basis=="queued-to-lead" -- легален ТОЛЬКО для пары
       agent=critic (класс критика, ярус opus) И by ∈ {"sonnet",
       "opus"} (для by=sonnet -- очередь легальна ИМЕННО критик-классу,
       НЕ builder-классу: у sonnet-координатора builder-класс легален
       только через basis="critic" -- это ровно AO3-кейс,
       test_matrix_sonnet_by_builder_queued_to_lead_fails_ao3_case; для
       by=opus -- очередь легальна критик-классу как равному ярусу).
       agent=scout/builder с basis="queued-to-lead" не проходит эту
       ветку (scout уже закрыт ok_tier почти всегда; builder -- нет,
       собственно AO3-дыра).
    е) Любой иной basis (включая отсутствие) -- FAIL с общим
       D-0058-сообщением.

    СУЖЕНИЕ ПОВЕРХНОСТИ (t-323, критик 2026-07-28): энум-гейт формы by
    действует ТОЛЬКО на accepted с agent ∈ {scout,builder,critic,designer}
    (2026-07-30: designer добавлен в AGENT_TIER, тот же класс); вне
    гейта (записанные РЕШЕНИЯ, не пропуски): rejected -- by без
    матричной проверки (буквальное чтение спеки, см. начало правила
    11); agent=lead -- легален не-ярусный by (живой прецедент
    by="operator" в logs/routing-log.jsonl -- оператор есть вершина
    иерархии, R11a); agent вне AGENT_TIER -- матрица вообще не
    определена спекой (return None до всех веток). Кандидаты
    форм-валидации этих трёх соседей -- очередь калибровки №5 (пункт
    ставит координатор своим ходом).

12. Любой FAIL -> exit 1, по каждой нарушившей строке -- номер строки,
    event/task_id, какая проверка упала. Крэш валидатора (исключение,
    не FAIL валидации) -> exit 2 с трейсбеком (fail-closed, как
    mechanism_gate: cм. main()).

STANDALONE-режим (t-151, 2026-07-16): фикс класса «enforcement врёт ОК
вне своей среды» -- прецедент трижды подтверждён (экзамены №5-B/№6-B/
№8-t3, docs/tasks/2026-07-16_policy-as-code-design.md): в не-git
песочнице is_journal_staged() раньше молча возвращала False (git-вызов
падал/возвращал ошибку, но её returncode не проверялся -- пустой stdout
неотличим от «git ответил: ничего не staged»), из-за чего _main() тихо
делал exit 0 БЕЗ единой проверки -- ложный «валиден».

 A. Автодетект: _git_available() отдельным вызовом (`git rev-parse
    --is-inside-work-tree`) проверяет, что git-плюмбинг РЕАЛЬНО ответил
    (репо существует, бинарник найден, returncode==0). Это НЕ трогает
    is_journal_staged() -- штатный git-путь (репо есть, работает, но
    ИМЕННО этот файл не staged в текущем коммите) остаётся, как был,
    молчаливым exit 0 (легитимный no-op, а не баг: нечего проверять в
    ЭТОМ коммите -- нарушение п.4 спеки t-151, главный риск правки,
    было бы менять этот путь).
 B. git недоступен (не репо / бинарник отсутствует) ИЛИ явный флаг
    --standalone -> _run_standalone(): читает JOURNAL_PATH ПРЯМО с
    диска (не через git show), печатает громкую строку "STANDALONE
    MODE (git недоступен): проверен весь файл, N строк" ПЕРЕД любым
    exit-кодом, затем валидирует ВСЕ строки файла через тот же decide()
    -- append-only тривиально пропускается (decide(text, "", now):
    check_append_only против пустого HEAD проходит вакуумно, ни одна
    строка старого файла не теряется на пустом списке), с явной
    строкой "standalone: append-only не проверяем, нет git-базы"
    (append-only в принципе непроверяем без HEAD -- не то же самое,
    что «не проверяли»). Файла нет вовсе -> отдельная честная строка
    "нет файла журнала" + exit 0 (это факт о среде, не no-op: строка
    напечатана, проверка признана невозможной явно, а не молча).
 C. decide() и validate_new_lines() НЕ ИЗМЕНЕНЫ -- standalone
    переиспользует их как есть (нулевой риск для существующего
    покрытия и для штатного pre-commit пути).
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
import traceback
from pathlib import Path

# Оба потока: тексты отказа гейта -- кириллица и в stdout, и в stderr;
# без reconfigure Windows-консоль искажает их (класс найден в AO3-твине,
# их задача e4-impact-selection 2026-07-14; ось 1 SIBLING_MAP -- фикс парный,
# эталон -- tools/mechanism_gate.py). errors="replace" (порт AO3 «Мелкое
# хозяйство» п.1, 2026-07-18): голый encoding="utf-8" оставлял
# errors="strict" -- replace убирает последний шанс ValueError на
# повторной кодировке без потери диагностируемости (гейт печатает текст,
# не бинарные данные).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# D-0099: Lead-привязка (roles.lead в delegation.config.yaml) переезжает
# с fable на другую модель -- resolve_lead_binding()/lead_family() и
# CONFIG_PATH уже живут в mechanism_gate.py (тот же дом enforcement-цепочки,
# D-0043 ось 1); переиспользуем их парсер, не дублируем (см. правило 11
# ниже, ветка а2). B6 (пересдача, 2026-08-04): импорт обёрнут в
# try/except ImportError -- mg=None -> ветка а2 молча выключена (то же
# сегодняшнее поведение, что и без конфига вовсе). Симметрично
# session_context.py (тот же fail-open паттерн для sibling-импорта).
# Мотив: tools/journal_echo.py импортирует journal_validator СНАРУЖИ
# своего собственного fail-open try/except (см. его докстринг) -- если
# интерпретатор, из которого запускается хук, лишён PyYAML (mechanism_gate
# требует его на верхнем уровне), падение импорта journal_validator's
# уронило бы весь хук ДО первой же строки этого модуля, а не только
# ветку а2.
try:
    import mechanism_gate as mg
except ImportError:
    mg = None

JOURNAL_PATH = "logs/routing-log.jsonl"

EVENTS = {
    "delegated", "accepted", "rejected", "escalated", "decomposable",
    "dispatch_skipped", "defect_found", "lead_degraded", "lead_restored",
    "journal_created", "calibrated",
}
MODEL_REQUIRED_EVENTS = {"delegated", "escalated", "accepted", "rejected"}
TASK_ID_REQUIRED_EVENTS = {"delegated", "accepted", "rejected", "escalated", "defect_found"}
FAILURE_CLASSES = {"spec", "capability", "recon", "tooling"}
TIER_ORDER = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
AGENT_TIER = {
    "scout": "haiku", "builder": "sonnet", "critic": "opus",
    # designer добавлен 2026-07-30: designer-функция привязана к opus
    # (см. .claude/agents/designer.md, model: opus) -- тот же ярус, что
    # critic. Класс дыры до этой правки: agent="designer" был вне
    # AGENT_TIER, матрица D-0058 молча не применялась к его accepted-
    # строкам (см. return None у "agent not in AGENT_TIER" ниже).
    "designer": "opus",
}
# Класс верхне-среднего яруса (2026-07-30, решение Lead после критика):
# ветка (5) basis="queued-to-lead" была ключена на буквальное имя
# agent=="critic" -- сужение по ИМЕНИ, а не по КЛАССУ. designer несёт
# тот же ярус (opus), ту же координаторскую семантику ветки (5) --
# очередь к Lead легальна ОБОИМ при координаторе не строго выше.
# basis="critic" при этом НЕ распространяется на designer тем же
# путём (ветка (4) уже и так работает по числовому сравнению ярусов,
# не по имени -- критик того же яруса не поднимает приёмку выше opus,
# это уже верно и для designer без отдельной правки).
QUEUED_TO_LEAD_AGENTS = {"critic", "designer"}
# Известные строковые значения non-judge basis -- ЧИСТЫЙ enum/справка
# (внешние потребители: WEEKLY_CALIBRATION_PROTOCOL.md, log_append.py),
# больше НЕ используется как проверка легальности "basis in
# BASIS_VALUES" -- с batch B7 (2026-07-24) легальность решает пара
# (by, agent) в _matrix_d0058_violation, не голое членство (закрыта
# утечка AO3 07-24: basis=queued-to-lead проходило членство для ЛЮБОГО
# by/agent, включая builder-класс у sonnet-координатора).
BASIS_VALUES = {"critic", "queued-to-lead"}
JUDGE_BASIS_VALUE = "judge"
# Лист-классы, для которых basis "judge" легален (правило 11 / CLAUDE.md
# «Leaf routing», R13/D-0087-эквивалент): "recon, or implementation to a
# written spec".
LEAF_CATEGORIES = {"recon", "implementation"}

# D-0099: сентинел "config_text не передан явно" -- decide() отличает
# "вызывающий явно передал config_text=None" (нет конфига/парсер вернёт
# дефолт "fable" -- используется тестами) от "вызывающий вообще не знает
# про config_text" (реальные CLI-входы: main()/_run_standalone()/
# journal_echo.py, все зовут decide() тремя позиционными аргументами) --
# только второй случай лениво читает delegation.config.yaml с диска.
_CONFIG_TEXT_UNSET = object()
# Кэш реального чтения -- "один раз за процесс" (спека: "лениво/кэшировано").
# Не участвует в инъекции тестов: тест, которому нужен конкретный
# config_text, передаёт его явно и никогда не задевает этот кэш.
_cached_real_config_text = _CONFIG_TEXT_UNSET


def _read_real_config_text() -> str | None:
    """Ленивое кэшированное чтение REPO/delegation.config.yaml -- та же
    форма, что mechanism_gate.main() использует для CONFIG_PATH (файла нет
    -> None -> mg.resolve_lead_binding(None) == "fable", регресс-пин).
    B6: mg is None (mechanism_gate недоступен -- см. top-level try/except
    выше) -> None без попытки чтения -- ветка а2 молча выключена, то же
    сегодняшнее поведение, что и при отсутствии файла."""
    global _cached_real_config_text
    if mg is None:
        return None
    if _cached_real_config_text is _CONFIG_TEXT_UNSET:
        path = mg.CONFIG_PATH
        _cached_real_config_text = (
            path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        )
    return _cached_real_config_text


TASK_ID_RE = re.compile(r"^t-(\d{3,})$")
# Маркер замены умершего воркера (2026-07-15, правило 9в2): literal
# "replaces_worker:" + непустой хэндл = первый non-whitespace токен сразу
# за двоеточием (формат совпадает с существующими worker_ref -- 'cli:...',
# 'agent:...' -- без пробелов внутри).
REPLACES_WORKER_RE = re.compile(r"replaces_worker:(\S+)")
# ISO без таймзоны: 'YYYY-MM-DDTHH:MM:SS' с опциональными микросекундами,
# БЕЗ 'Z'/смещения -- таймзона запрещена спекой (иначе пропадает
# однозначность монотонности между строками разных смещений).
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")


def parse_ts(ts: str):
    if not isinstance(ts, str) or not TS_RE.match(ts):
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def split_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _try_parse_obj(line: str):
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def extract_task_ids(lines: list[str]) -> set[str]:
    """Все task_id (валидного формата t-NNN), встреченные в ЛЮБОМ событии
    этих строк -- используется и для множества "существующих выше", и
    как основа для max(...)+1."""
    ids = set()
    for line in lines:
        obj = _try_parse_obj(line)
        if obj is None:
            continue
        tid = obj.get("task_id")
        if isinstance(tid, str) and TASK_ID_RE.match(tid):
            ids.add(tid)
    return ids


def max_task_num(ids: set[str]) -> int:
    nums = [int(TASK_ID_RE.match(i).group(1)) for i in ids]
    return max(nums) if nums else 0


def extract_replaces_worker(notes) -> str | None:
    """Правило 9(в2): вытаскивает хэндл из маркера "replaces_worker:<хэндл>"
    в notes -- literal-подстрока + первый non-whitespace токен сразу за
    двоеточием. None, если маркера нет (notes не строка или подстрока
    отсутствует)."""
    if not isinstance(notes, str):
        return None
    m = REPLACES_WORKER_RE.search(notes)
    return m.group(1) if m else None


def _harvest_line_into(idx: int, event, task_id, agent, worker_ref, delegated_agents: dict, closed_tasks: set,
                        rejected_tasks: set, task_worker_refs: dict, rejected_by_agent: dict,
                        last_delegated_idx: dict, signal_log: dict) -> None:
    """Правило 9(б/в/в2) state: обновляет per-task_id историю ОДНОЙ строкой
    (используется и для затравки из HEAD, и построчно для новых строк --
    порядок вызовов = порядок появления строк в файле, так что состояние
    на момент проверки строки N отражает ровно "всё выше по файлу").
    task_worker_refs копит ВСЕ worker_ref всех delegated (любого agent)
    этого task_id -- правило 9в2 ищет заявленный прежний worker_ref именно
    в этом множестве, не только среди строк того же agent.

    idx -- 0-based позиция строки В ПОЛНОМ ФАЙЛЕ (HEAD-строки: 0..len(head)-1
    по порядку; новые строки продолжают счёт -- см. вызов в
    validate_new_lines: len(head_lines)+idx-в-new_lines). Дыра B3
    (2026-08-10, порт AO3 AT-BUG-034, правило 9в): rejected_by_agent
    (task_id -> множество agent, чей результат отклонён на этой задаче)
    и signal_log (task_id -> список (idx, kind, agent) сигналов новой
    версии: kind="delegated" на КАЖДЫЙ delegated, kind="lead_rejected" на
    rejected с agent=lead, kind="escalated" на escalated) -- вместе с
    last_delegated_idx (task_id, agent) -> idx ПОСЛЕДНЕГО delegated этого
    agent на этом task_id -- дают _has_new_version_signal() материал для
    различения "свой" (i) и "чужой" (ii) rejected из правила 9в."""
    if not (isinstance(task_id, str) and TASK_ID_RE.match(task_id)):
        return
    if event == "delegated" and isinstance(agent, str) and agent:
        delegated_agents.setdefault(task_id, set()).add(agent)
        if isinstance(worker_ref, str) and worker_ref.strip():
            task_worker_refs.setdefault(task_id, set()).add(worker_ref.strip())
        last_delegated_idx[(task_id, agent)] = idx
        signal_log.setdefault(task_id, []).append((idx, "delegated", agent))
    elif event == "accepted":
        closed_tasks.add(task_id)
    elif event == "rejected":
        rejected_tasks.add(task_id)
        if isinstance(agent, str) and agent:
            rejected_by_agent.setdefault(task_id, set()).add(agent)
            if agent == "lead":
                signal_log.setdefault(task_id, []).append((idx, "lead_rejected", agent))
    elif event == "escalated":
        signal_log.setdefault(task_id, []).append((idx, "escalated", agent))


def harvest_task_state(lines: list[str]):
    """Затравка состояния правила 9(б/в/в2) из HEAD-версии (или любого
    префикса строк) -- (delegated_agents, closed_tasks, rejected_tasks,
    task_worker_refs, rejected_by_agent, last_delegated_idx, signal_log).
    idx внутри lines -- 0-based позиция В ЭТОМ СПИСКЕ (для HEAD-затравки
    это позиция в head_lines, ровно 0..len(head_lines)-1 -- см. докстринг
    _harvest_line_into про продолжение счёта для новых строк)."""
    delegated_agents: dict[str, set] = {}
    closed_tasks: set = set()
    rejected_tasks: set = set()
    task_worker_refs: dict[str, set] = {}
    rejected_by_agent: dict[str, set] = {}
    last_delegated_idx: dict[tuple, int] = {}
    signal_log: dict[str, list] = {}
    for idx, line in enumerate(lines):
        obj = _try_parse_obj(line)
        if obj is None:
            continue
        _harvest_line_into(idx, obj.get("event"), obj.get("task_id"), obj.get("agent"), obj.get("worker_ref"),
                           delegated_agents, closed_tasks, rejected_tasks, task_worker_refs,
                           rejected_by_agent, last_delegated_idx, signal_log)
    return (delegated_agents, closed_tasks, rejected_tasks, task_worker_refs,
            rejected_by_agent, last_delegated_idx, signal_log)


def _has_new_version_signal(task_id: str, agent, after_idx: int, signal_log: dict) -> bool:
    """Правило 9(в-ii), дыра B3 (порт AO3 AT-BUG-034): True, если в
    signal_log[task_id] есть сигнал СТРОГО ПОСЛЕ after_idx (= idx
    последнего delegated ИМЕННО этого agent на этом task_id) одного из
    трёх видов -- (1) delegated ДРУГОГО agent (kind_agent != agent), (2)
    rejected agent=lead (kind="lead_rejected"), (3) escalated ДРУГОГО
    agent (kind="escalated", kind_agent != agent -- Ф5, 2026-08-10, дыра
    B3 пересдача, критик-проба H2: без этого сужения агент мог сам
    записать escalated на СВОЮ же задачу и тем же ходом легализовать
    свой же повторный вход -- самолегализация петлёй; симметрично
    сигналу (1), у AO3 сигнал заякорен на эскалацию к полному Lead,
    здесь якорь -- "другой agent", не "другая модель"). idx <= after_idx
    -- сигнал из БОЛЕЕ РАННЕГО раунда (до последнего собственного
    delegated входящего agent) -- протух, не считается (см. тесты
    test_b3_stale_*)."""
    for idx, kind, kind_agent in signal_log.get(task_id, ()):
        if idx <= after_idx:
            continue
        if kind in ("delegated", "escalated") and kind_agent != agent:
            return True
        if kind == "lead_rejected":
            return True
    return False


def _last_head_ts(head_lines: list[str]):
    """ts ПОСЛЕДНЕЙ строки HEAD-версии (правило 10: монотонность считается
    от неё, а не от максимума по файлу -- журнал append-only, поэтому
    последняя строка HEAD и есть хронологически последняя из старых)."""
    if not head_lines:
        return None
    obj = _try_parse_obj(head_lines[-1])
    if obj is None:
        return None
    return parse_ts(obj.get("ts"))


def check_append_only(staged_lines: list[str], head_lines: list[str]):
    """Правило 1: staged обязана начинаться с head как префикс (существующие
    строки не изменены и не удалены). Возвращает (ok, message)."""
    if len(staged_lines) < len(head_lines):
        return False, (
            f"append-only: staged содержит МЕНЬШЕ строк ({len(staged_lines)}) "
            f"чем HEAD ({len(head_lines)}) -- существующие строки удалены"
        )
    for i, head_line in enumerate(head_lines):
        if staged_lines[i] != head_line:
            return False, (
                f"append-only: строка {i + 1} расходится с HEAD -- "
                "существующие строки нельзя менять, только добавлять в конец"
            )
    return True, ""


def _matrix_d0058_violation(event: str, agent, by: str, obj: dict,
                             config_text: str | None = None) -> str | None:
    """Правило 11 (batch B7, 2026-07-24: пары-легальности вместо
    членства-в-множестве). Возвращает текст нарушения или None.
    Применяется ТОЛЬКО к accepted (буквальное чтение спеки: "accepted
    легален, если..."; rejected несёт "by" без дальнейшей
    tier/basis-проверки).

    Порядок проверок сознательно НЕ if-каскад "первый матч побеждает
    без объяснения" -- каждая ветка читается против одной строки
    таблицы CLAUDE.md «Role ≠ tier» (см. правило 11 в модульном
    докстринге для полной таблицы пар и цитат):

    1) basis=="judge" -- отдельный, не координаторский путь приёмки
       (калиброванный судья, R13/D-0087): легален ТОЛЬКО на лист-класс
       category, НЕЗАВИСИМО от tier(by) -- проверяется первым, чтобы
       floor п.3 его не перехватывал (правка t-276 сохранена как есть).
    2) ok_tier: tier(by) > tier(agent) -- легально при любом basis.
    3) FLOOR: tier(by) известен и СТРОГО ниже sonnet (т.е. by=="haiku")
       -- FAIL безусловно, ни один basis (кроме уже отработавшего
       "judge") не спасает ("below Sonnet: no coordination is provided
       for"). B2 (пересдача, критик-блокер): Lead-привязка (ветка 3b
       ниже) проверяется ПОСЛЕ floor, не до -- floor в матрице CLAUDE.md
       безусловен, привязка на haiku (гипотетическая) не спасает
       haiku-by от floor ни в каком случае.
    3b) (D-0099, была "1b"/"а2") Lead-привязка принимает финально БЕЗ
       basis, даже на РАВНОМ ярусе -- полный Lead определяется
       ПРИВЯЗКОЙ, не именем "fable"; ПОСЛЕ floor -- см. правку B2 выше.
    4) basis=="critic": легален, только если tier("opus") строго выше
       tier(agent) -- т.е. agent класса scout/builder, не critic.
    5) basis=="queued-to-lead": легален ТОЛЬКО для agent класса critic
       И by ∈ {"sonnet", "opus"}.
    6) иначе -- FAIL с общим D-0058-сообщением."""
    if event != "accepted":
        return None
    if agent == "lead":
        return None  # Lead-tier работа: presence "by" уже проверена выше
    if agent not in AGENT_TIER:
        return None  # неизвестный agent -- матрица не определена спекой
    if by not in TIER_ORDER:
        # Порт AO3-фикса (их калибровка №4, коммит 30e79c8):
        # энум-проверка формы ("by -- известный ярус вообще") предшествует
        # ЛЮБОЙ семантике матрицы, включая judge (t-323) -- basis не может
        # легализовать приёмку от неизвестного принимающего; ok_tier/floor
        # молчали при by_tier=None, а basis="critic"/"judge" не смотрели
        # by вовсе -- дыра AO3 07-24 закрыта здесь.
        return (
            f"D-0058: by={by!r} не является известным ярусом "
            f"({sorted(TIER_ORDER)}) — basis не может легализовать приёмку "
            f"от неизвестного принимающего (энум-проверка формы предшествует "
            f"семантике матрицы; порт AO3-фикса 30e79c8)"
        )
    agent_tier_name = AGENT_TIER[agent]
    agent_tier = TIER_ORDER[agent_tier_name]
    by_tier = TIER_ORDER.get(by)
    basis = obj.get("basis")

    # (1) judge -- отдельный путь, не координаторский; проверяется до
    # tier/floor, category решает всё. СУЖЕНИЕ (2026-07-30, критик):
    # судья принимает ТОЛЬКО лист-класс ИСПОЛНИТЕЛЕЙ (agent ∈
    # {scout,builder}) -- спеки (designer) и ревью (critic) ему
    # запрещены политикой независимо от category (до этой правки
    # agent=designer + basis=judge + category=implementation ложно
    # проходил, т.к. проверялась только category, не agent). Порядок:
    # category-гейт проверяется ПЕРВЫМ (нелистовая category фейлит для
    # ЛЮБОГО agent, включая scout/builder, -- регресс-пин прежних
    # тестов), agent-гейт -- ВТОРЫМ, только когда category уже лист.
    if basis == JUDGE_BASIS_VALUE:
        if obj.get("category") not in LEAF_CATEGORIES:
            return (
                f"R13/D-0087: basis \"judge\" is legal only for leaf-class "
                f"dispatches (recon/implementation), got category={obj.get('category')!r}"
            )
        if agent not in ("scout", "builder"):
            return (
                f"R13/D-0087: basis \"judge\" is legal only for agent∈"
                f"{{scout,builder}} (leaf-class EXECUTORS) -- agent={agent!r} "
                f"is not eligible for judge acceptance regardless of category "
                f"(specs and reviews stay outside the judge's remit by policy)"
            )
        return None

    # (2) ok_tier -- строго выше, легально при любом basis (или без него).
    if by_tier is not None and by_tier > agent_tier:
        return None

    # (3) FLOOR: by известного яруса СТРОГО ниже sonnet -- координация
    # не предусмотрена ни при каком basis (Role != tier matrix: "below
    # Sonnet: no coordination is provided for"). Развилка с буквой ядра
    # ("carries a higher tier's input") документирована и решена в
    # пользу floor -- см. правило 11 модульного докстринга. B2
    # (пересдача, критик-блокер): floor БЕЗУСЛОВЕН и стоит ДО ветки 3b
    # (Lead-привязка) -- гипотетическая привязка Lead на haiku не спасает
    # haiku-by от floor, ветка 3b его больше не перехватывает.
    if by_tier is not None and by_tier < TIER_ORDER["sonnet"]:
        return (
            f"D-0058: by={by!r} -- ярус ниже sonnet, координация не "
            f"предусмотрена ни при каком basis={basis!r} (Role != tier "
            f"matrix: 'below Sonnet: no coordination is provided for'); "
            f"agent={agent!r} не может быть принят этим by"
        )

    # (3b, D-0099, была "1b"/"а2", 2026-08-04, B2 переставлена ПОСЛЕ floor
    # в пересдаче): Lead-привязка принимает финально БЕЗ basis, даже на
    # РАВНОМ ярусе -- полный Lead определяется ПРИВЯЗКОЙ (delegation.
    # config.yaml), не именем "fable": by ДОЛЖЕН литерально совпасть с
    # ярусным семейством привязки (mg.lead_family -- None для не-Claude
    # привязки, тогда эта ветка не активируется вовсе), И tier(by) >=
    # tier(agent) НЕСТРОГО -- именно нестрогость и есть отличие от
    # ok_tier: вердикт рождается в независимом контексте (отдельная
    # сессия/subagent на ярусе привязки), независимость контекста
    # заменяет строгое численное превосходство модели при равном ярусе.
    # По конструкции (floor уже отработал выше) by_tier здесь либо None,
    # либо >= tier(sonnet) -- гипотетическая привязка на haiku никогда не
    # долетает досюда с известным by_tier < sonnet, floor её уже отсёк.
    # B6: mg is None (mechanism_gate недоступен) -- ветка молча выключена.
    if mg is not None:
        binding = mg.resolve_lead_binding(config_text)
        lead_binding_family = mg.lead_family(binding)
        if lead_binding_family is not None and by == lead_binding_family and by_tier >= agent_tier:
            return None

    # (4) basis=="critic" -- легален, если критик (opus) строго выше
    # agent (agent класса scout/builder). Числовое сравнение ярусов
    # (не имя agent) -- уже верно закрывает designer без отдельной
    # правки: designer тоже яруса opus, tier("opus") > tier("opus")
    # ложно, тот же отказ, что и для agent="critic" сейчас.
    if basis == "critic":
        if TIER_ORDER["opus"] > agent_tier:
            return None
        return (
            f"D-0058: agent={agent!r} (ярус {agent_tier_name}) принят с "
            f"basis='critic', но критик (opus) не строго выше яруса "
            f"исполнителя -- basis='critic' не поднимает приёмку выше "
            f"собственного opus-яруса; легальный путь для agent={agent!r} "
            f"-- by строго выше opus (by='fable'), либо "
            f"basis='queued-to-lead' при by∈{{sonnet,opus}}"
        )

    # (5) basis=="queued-to-lead" -- легален КЛАССУ верхне-среднего
    # яруса (QUEUED_TO_LEAD_AGENTS = {critic, designer}, см. её
    # докстринг выше) у by∈{sonnet,opus} (AO3-кейс: builder-класс у
    # sonnet-координатора НЕ проходит -- легален только через
    # basis='critic').
    if basis == "queued-to-lead":
        if agent in QUEUED_TO_LEAD_AGENTS and by in ("sonnet", "opus"):
            return None
        return (
            f"D-0058: agent={agent!r} принят by={by!r} с "
            f"basis='queued-to-lead' -- для {agent!r}-класса у "
            f"{by!r}-координатора легален только basis='critic' (или "
            f"judge на leaf-implementation, если category -- лист-класс, "
            f"и agent∈{{scout,builder}}); очередь (queued-to-lead) "
            f"доступна только классу {sorted(QUEUED_TO_LEAD_AGENTS)}"
        )

    # (6) прочее -- общий D-0058 отказ.
    return (
        f"D-0058: agent={agent!r} принят by={by!r} (не строго выше яруса "
        f"исполнителя) и нет валидного basis (нужно critic/queued-to-lead "
        f"по паре, либо judge на лист-класс -- category ∈ "
        f"recon/implementation, R13/D-0087)"
    )


def validate_new_lines(new_lines: list[str], head_lines: list[str],
                        now: datetime.datetime,
                        config_text: str | None = None) -> list[str]:
    violations: list[str] = []
    seen_task_ids = extract_task_ids(head_lines)
    max_num = max_task_num(seen_task_ids)
    last_ts = _last_head_ts(head_lines)
    now_limit = now + datetime.timedelta(minutes=10)
    (delegated_agents, closed_tasks, rejected_tasks, task_worker_refs,
     rejected_by_agent, last_delegated_idx, signal_log) = harvest_task_state(head_lines)

    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, TypeError) as e:
            violations.append(f"line {line_no}: невалидный JSON ({e})")
            continue
        if not isinstance(obj, dict):
            violations.append(f"line {line_no}: не JSON-объект")
            continue

        event = obj.get("event")
        task_id = obj.get("task_id")
        agent = obj.get("agent")
        tag = f"line {line_no} event={event!r} task_id={task_id!r}"

        ts = obj.get("ts")
        category = obj.get("category")
        notes = obj.get("notes")

        if not isinstance(ts, str) or not ts:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'ts'")
        if not isinstance(event, str) or not event:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'event'")
        if not isinstance(agent, str) or not agent:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'agent'")
        if not isinstance(category, str) or not category:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'category'")
        if not isinstance(notes, str) or not notes.strip():
            violations.append(f"{tag}: отсутствует/пустое обязательное поле 'notes'")

        if isinstance(event, str) and event and event not in EVENTS:
            violations.append(f"{tag}: 'event' не из enum ({event!r})")

        if event in MODEL_REQUIRED_EVENTS:
            model = obj.get("model")
            if not isinstance(model, str) or not model:
                violations.append(f"{tag}: 'model' обязателен для event={event}")

        if event in TASK_ID_REQUIRED_EVENTS:
            if not isinstance(task_id, str) or not task_id:
                violations.append(f"{tag}: 'task_id' обязателен для event={event}")
            elif not TASK_ID_RE.match(task_id):
                violations.append(f"{tag}: task_id {task_id!r} не соответствует формату t-NNN (3+ цифр)")

        if event == "rejected":
            attempt = obj.get("attempt")
            if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
                violations.append(f"{tag}: 'attempt' обязан быть целым >=1")
            failure_class = obj.get("failure_class")
            if failure_class not in FAILURE_CLASSES:
                violations.append(
                    f"{tag}: 'failure_class' обязан быть одним из {sorted(FAILURE_CLASSES)}"
                )

        if event == "accepted" and agent == "builder":
            witness = obj.get("witness")
            if not isinstance(witness, str) or not witness.strip():
                violations.append(f"{tag}: 'witness' обязателен (непустая строка) для accepted+agent=builder")

        if event == "delegated":
            worker_ref = obj.get("worker_ref")
            if not isinstance(worker_ref, str) or not worker_ref.strip():
                violations.append(
                    f"{tag}: 'worker_ref' обязателен (непустая строка) для delegated (D-0076)"
                )

        if event == "defect_found":
            ref = obj.get("ref")
            if not isinstance(ref, str) or not ref:
                violations.append(f"{tag}: 'ref' обязателен (непустой) для defect_found")

        if event in ("accepted", "rejected"):
            by = obj.get("by")
            if not isinstance(by, str) or not by:
                violations.append(f"{tag}: 'by' обязателен (непустой) для {event} (матрица D-0058)")
            else:
                mv = _matrix_d0058_violation(event, agent, by, obj, config_text)
                if mv:
                    violations.append(f"{tag}: {mv}")

        valid_tid = isinstance(task_id, str) and TASK_ID_RE.match(task_id)
        if event == "delegated" and valid_tid:
            if task_id not in seen_task_ids:
                # (а) новая задача -- обязана быть ровно max+1.
                expected = max_num + 1
                actual = int(TASK_ID_RE.match(task_id).group(1))
                if actual != expected:
                    violations.append(
                        f"{tag}: новизна task_id нарушена -- ожидался t-{expected:03d} (max+1), получен {task_id}"
                    )
            elif task_id in closed_tasks:
                # (г) reopen запрещён -- коллизия = две задачи (D-0060).
                violations.append(
                    f"{tag}: delegated на ЗАКРЫТУЮ задачу {task_id!r} (выше уже есть accepted) -- "
                    "reopen запрещён, коллизия считается двумя задачами (D-0060)"
                )
            else:
                prior_agents = delegated_agents.get(task_id, set())
                if isinstance(agent, str) and agent and agent not in prior_agents:
                    pass  # (б) continuation-диспатч другого яруса -- легально
                else:
                    attempt = obj.get("attempt")
                    valid_attempt = (isinstance(attempt, int) and not isinstance(attempt, bool)
                                      and attempt >= 2)
                    # Дыра B3 (2026-08-10, порт AO3 AT-BUG-034): "чужой" rejected
                    # (agent, чей результат отклонён, ОТЛИЧАЕТСЯ от входящего agent)
                    # легализует вход ТОЛЬКО с сигналом новой версии ПОСЛЕ последнего
                    # delegated этого agent (правило 9в-ii) -- см. _has_new_version_signal.
                    own_rejected = isinstance(agent, str) and agent in rejected_by_agent.get(task_id, set())
                    foreign_rejected = task_id in rejected_tasks and not own_rejected
                    if valid_attempt and own_rejected:
                        retry_ok = True  # (в-i) self-retry -- как раньше, без доп. условий
                    elif valid_attempt and foreign_rejected:
                        last_own_idx = last_delegated_idx.get((task_id, agent))
                        retry_ok = (last_own_idx is not None
                                    and _has_new_version_signal(task_id, agent, last_own_idx, signal_log))
                    else:
                        retry_ok = False
                    replaces_handle = extract_replaces_worker(notes)
                    if retry_ok:
                        pass  # (в) легальный ретрай после rejected
                    elif replaces_handle is not None:
                        prior_refs = task_worker_refs.get(task_id, set())
                        if replaces_handle in prior_refs:
                            pass  # (в2) легальная замена умершего воркера
                        else:
                            violations.append(
                                f"{tag}: replaces_worker={replaces_handle!r} не встречается ни в "
                                f"одном предыдущем delegated task_id={task_id!r} -- фиктивная "
                                "замена запрещена (правило 9в2)"
                            )
                    else:
                        # (в) не выполнены условия ретрая, маркера замены нет -> (г) дубль-паттерн t-029.
                        # Ф3 (2026-08-10, дыра B3 пересдача, критик-проба J/J'): valid_attempt
                        # проверяется ПЕРВЫМ -- если attempt сам по себе отсутствует/невалиден,
                        # сообщение обязано называть ИМЕННО ЭТО, а не рассуждать о rejected/сигналах
                        # (даже если foreign_rejected формально True и свежий сигнал ЕСТЬ -- отсутствие
                        # attempt само по себе достаточная и единственная причина отказа здесь, текст
                        # не должен утверждать ложь "сигнала нет", когда сигнал есть). Тексты отказа
                        # этого гейта читает человек в момент отказа -- тот же мотив, что и у кодировки.
                        if not valid_attempt:
                            reason = (
                                "поле 'attempt' отсутствует или невалидно (обязано быть целым >=2 "
                                "для повторного delegated по существующему открытому task_id) -- "
                                "остальные условия (наличие/чуждость rejected, сигнал новой версии) "
                                "не проверяются, пока сам attempt некорректен"
                            )
                        elif foreign_rejected:
                            reason = (
                                "на task_id есть rejected, но НЕ agent'а, который входит повторно "
                                "(\"чужой\" rejected, правило 9в-ii) -- легален только если ПОСЛЕ "
                                "последнего delegated ЭТОГО agent появился сигнал новой версии "
                                "(новый delegated другого agent / rejected agent=lead / escalated "
                                "на этот task_id); сигнала нет, либо он из более раннего раунда и "
                                "протух -- дыра B3 (порт AO3 AT-BUG-034)"
                            )
                        else:
                            reason = "attempt валиден, но rejected для этого task_id нет вовсе (ни своего, ни чужого)"
                        violations.append(
                            f"{tag}: повторный delegated тем же agent={agent!r} по task_id={task_id!r} "
                            f"{reason} -- запрещённый дубль "
                            "(класс t-029, D-0060); легальная альтернатива -- маркер "
                            "'replaces_worker:<прежний worker_ref>' в notes при замене умершего "
                            "воркера без вердикта (правило 9в2)"
                        )
        elif event in ("accepted", "rejected", "escalated", "defect_found") and valid_tid:
            if task_id not in seen_task_ids:
                violations.append(
                    f"{tag}: task_id {task_id!r} не ссылается ни на что существующее выше в файле"
                )

        _harvest_line_into(line_no - 1, event, task_id, agent, obj.get("worker_ref"), delegated_agents,
                           closed_tasks, rejected_tasks, task_worker_refs, rejected_by_agent,
                           last_delegated_idx, signal_log)

        parsed_ts = parse_ts(ts) if isinstance(ts, str) else None
        if isinstance(ts, str) and ts and parsed_ts is None:
            violations.append(f"{tag}: ts {ts!r} не ISO-формат без таймзоны")
        if parsed_ts is not None:
            if last_ts is not None and parsed_ts < last_ts:
                violations.append(
                    f"{tag}: ts не монотонен -- {parsed_ts.isoformat()} раньше предыдущего {last_ts.isoformat()}"
                )
            if parsed_ts > now_limit:
                violations.append(
                    f"{tag}: ts {ts!r} позже now+10мин ({now_limit.isoformat()}) -- "
                    "повествовательное будущее (F-29)"
                )
            last_ts = parsed_ts

        if valid_tid:
            seen_task_ids.add(task_id)
            num = int(TASK_ID_RE.match(task_id).group(1))
            if num > max_num:
                max_num = num

    return violations


def decide(staged_text: str | None, head_text: str | None,
           now: datetime.datetime | None = None,
           config_text=_CONFIG_TEXT_UNSET) -> tuple[int, list[str]]:
    """Чистое решение гейта -- тестируется без git (см. tools/test_journal_validator.py).

    config_text (D-0099): текст delegation.config.yaml для резолюции
    Lead-привязки (правило 11, ветка а2) -- ИНЪЕКТИРУЕМ явно (в т.ч.
    явный None -- "нет конфига", тот же дефолт парсера, что и раньше).
    Когда параметр вообще НЕ передан (сентинел _CONFIG_TEXT_UNSET -- все
    реальные CLI-вызовы: main()/_run_standalone()/tools/journal_echo.py,
    все зовут decide() тремя позиционными аргументами и НЕ знают про
    config_text), читает REPO/delegation.config.yaml с диска один раз за
    процесс (см. _read_real_config_text) -- файла нет сегодня ->
    resolve_lead_binding(None) == "fable", регресс-пин, а после того как
    Lead создаст файл, эти вызовы подхватят привязку без правки."""
    now = now or datetime.datetime.now()
    if config_text is _CONFIG_TEXT_UNSET:
        config_text = _read_real_config_text()
    staged_lines = split_lines(staged_text)
    head_lines = split_lines(head_text)
    ok, msg = check_append_only(staged_lines, head_lines)
    if not ok:
        return 1, [msg]
    new_lines = staged_lines[len(head_lines):]
    violations = validate_new_lines(new_lines, head_lines, now, config_text)
    if violations:
        return 1, violations
    return 0, []


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def is_journal_staged(journal_path: str = JOURNAL_PATH) -> bool:
    proc = _git("diff", "--cached", "--name-only")
    return journal_path in proc.stdout.splitlines()


def get_staged_text(journal_path: str = JOURNAL_PATH) -> str:
    """Префикс "./" в colon-path заставляет его резолвиться относительно
    cwd самого _git -- БЕЗ него голый ":<path>" резолвится относительно
    ВЕРШИНЫ того git-репо, внутри которого лежит cwd, что молча
    расходится с cwd-относительным резолвом всякий раз, когда cwd --
    подкаталог БОЛЬШЕГО репо, а не вершина сам по себе (см. докстринг
    gateway/lead_replay.py.git_preimage за тот же класс, эмпирически
    подтверждённый там же; в нашем репо cwd сам является вершиной, так
    что "./" здесь no-op)."""
    proc = _git("show", f":./{journal_path}")
    return proc.stdout if proc.returncode == 0 else ""


def get_head_text(journal_path: str = JOURNAL_PATH) -> str:
    """Тот же resolве-мотив "./", что get_staged_text выше."""
    proc = _git("show", f"HEAD:./{journal_path}")
    return proc.stdout if proc.returncode == 0 else ""


def _git_available() -> bool:
    """t-151 правило 1 (автодетект): True когда git-плюмбинг РЕАЛЬНО
    ответил -- отдельный однозначный вызов (`rev-parse
    --is-inside-work-tree`), а не побочный вывод is_journal_staged()
    (её returncode никогда не проверялся -- корень старого no-op-бага:
    "git упал" и "git ответил: пусто" давали неотличимый пустой stdout).
    Намеренно НЕ переиспользует is_journal_staged()/её git-вызов --
    отдельный маленький вызов, чтобы не трогать ни байта в протестированной
    штатной функции (регресс-риск п.4 спеки t-151)."""
    try:
        proc = _git("rev-parse", "--is-inside-work-tree")
    except (FileNotFoundError, OSError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _run_standalone(now: datetime.datetime, journal_path: str = JOURNAL_PATH) -> int:
    """t-151 правило 1/2: standalone-режим -- читает journal_path ПРЯМО
    с диска (git может быть вообще недоступен) и валидирует ВЕСЬ файл
    всеми проверками decide(), не требующими git-базы. decide(text, "",
    now) уже ровно это делает (append-only против пустого HEAD проходит
    вакуумно -- см. check_append_only; validate_new_lines видит КАЖДУЮ
    строку файла как "новую") -- переиспользуем decide() без изменений,
    не заводим вторую копию логики валидации. Громкая строка гарантирует:
    тихий exit 0 без единой проверки невозможен ни на одном под-пути --
    либо честное "нет файла журнала", либо заголовок STANDALONE MODE +
    N строк печатается ПЕРЕД любым exit 0/1."""
    path = Path(journal_path)
    if not path.exists():
        print(f"journal_validator: STANDALONE MODE -- нет файла журнала ({journal_path}), "
              "проверять нечего")
        return 0
    text = path.read_text(encoding="utf-8")
    lines = split_lines(text)
    print(f"STANDALONE MODE (git недоступен): проверен весь файл, {len(lines)} строк")
    print("standalone: append-only не проверяем, нет git-базы")
    code, violations = decide(text, "", now)
    if code:
        print(f"journal_validator: {journal_path} FAILED validation (standalone):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
    return code


def _main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    now = datetime.datetime.now()
    if "--standalone" in argv or not _git_available():
        return _run_standalone(now)
    if not is_journal_staged():
        return 0  # правило: файл не staged В РАБОЧЕМ git-репо -> молча exit 0
        # (легитимный no-op -- нечего проверять в этом коммите; git-контекст
        # ПРИ ЭТОМ доступен и работает, поэтому это НЕ путь standalone --
        # см. _git_available() выше и п.4 спеки t-151: этот путь не меняется)
    staged_text = get_staged_text()
    head_text = get_head_text()
    code, violations = decide(staged_text, head_text, now)
    if code:
        print(f"journal_validator: {JOURNAL_PATH} FAILED validation:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    """Внешняя граница: любое исключение (не FAIL валидации, а крэш самого
    валидатора) -> exit 2 с трейсбеком, fail-closed, как mechanism_gate."""
    try:
        return _main(argv)
    except Exception:
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
