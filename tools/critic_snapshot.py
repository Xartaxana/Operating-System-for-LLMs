"""critic_snapshot.py -- PreToolUse-хук: снимок дерева при КАЖДОМ
критик-вызове (kit v4 "full+gates", прогон N10).

STAGING_HQ ВАРИАНТ (t-159 п.7 -- АКТИВИРОВАН 2026-07-16; исходно staging-копия для
ревью и постановки Lead'ом, D-0069): единственное отличие от кита --
байтовое stdin-чтение (см. main()), тот же класс правки, что t-159
п.3/dispatch_gate.py. Логика снимка/семантика расхождения (ниже) НЕ
изменена.

Отличие от critic_gate.py (диет-kit v3): ЛИМИТА НЕТ -- полная
политика держит per-diff критика (правило 3), хук только фиксирует
факт: на момент каждого критик-вызова пишется/перезаписывается
.claude/critic_snapshot.json {ts, tree_hash, files_count}. Грейдер
сверяет ПОСЛЕДНИЙ снимок с финальным деревом: расхождение = "финал
не ревьюился" (неубираемый факт, не блок). Форма диспатча критика
проверяется отдельным dispatch_gate.py (лейбл) -- при его блоке
вызов не состоится и настоящий PreToolUse-side-effect снимка
безвреден: снимок перезапишется ближайшим состоявшимся вызовом;
след последнего РЕАЛЬНОГО ревью держится тем, что заблокированный
вызов не порождает работы критика.

tree_hash -- sha256 по отсортированному списку "{rel_path}:{sha256}"
всех файлов, исключая каталоги .claude/.git/__pycache__/.pytest_cache
(по имени на любой глубине) и logs/routing-log.jsonl -- алгоритм
байт-в-байт как compute_tree_hash() диет-kit v3 (t-150), грейдеры
переиспользуют ту же сверку.

t-159 (очередь v5 п.4) СЕМАНТИКА РАСХОЖДЕНИЯ -- явно, буквально:
"расхождение снимка = финал не совпал с ПОСЛЕДНИМ снимком критика"
означает КОНКРЕТНО "правки дерева ПОСЛЕ последнего Task/Agent-
ДИСПАТЧА критика" -- не "после последнего ревью критика" вообще.
Это различие материально: критик может РЕВЬЮИТЬ несколько раз в
одном и том же диспатче (агент читает, комментирует, читает снова)
без единого НОВОГО Task/Agent-вызова -- снимок пишется PreToolUse
ОДИН РАЗ, в момент диспатча, ДО того как критик реально что-то
прочитал в этом вызове; любые правки дерева, случившиеся ПОСЛЕ этого
момента диспатча, будут видны хуку как "расхождение", даже если
критик их честно перечитал в рамках ТОГО ЖЕ вызова (это уже
покрывает staleness внутри одного вызова -- хук не видит нутро
вызова, только before/after снимок относительно момента диспатча).

CONTINUATION-РЕ-РЕВЬЮ ХУКУ НЕВИДИМО (поправка 2026-07-16,
docs/tasks/2026-07-16_economy-exam-run7.md, разбор №10б-t1): если
координатор продолжает диалог с УЖЕ ЗАПУЩЕННЫМ критик-агентом через
инструмент continuation-канала (SendMessage к существующему
agent_id/session, НЕ новый Task/Agent-вызов) -- critic_snapshot.py НЕ
СРАБАТЫВАЕТ ВООБЩЕ, поскольку матчер этого хука (.claude/settings.json,
PreToolUse) зарегистрирован ТОЛЬКО на tool_name=="Task"|"Agent"
(main() явно фильтрует `if tool_name not in ("Task","Agent"): return 0`).
Живой прецедент №10б-t1: критик перепроверил дифф на 15 входах ПОСЛЕ
фикса через continuation того же critic-агента без нового
Task-диспатча -- снимок остался от ПЕРВОГО (исходного) диспатча,
грейдер увидел "расхождение" (финал не совпал со снимком), хотя
ре-ревью реально состоялось -- ОГРАНИЧЕНИЕ ИЗМЕРИТЕЛЯ, не факт "финал
не ревьюился".

ЭМПИРИЧЕСКАЯ ПРОВЕРКА "есть ли хук-точка на continuation-канал"
(t-159, метод -- тот же grep -a установленного бинарника claude.exe,
что дал схемы XWb/zWb в tools/dod_gate.py/tools/main_gate.py,
позитивный/негативный контроль F-30/F-34): ДА, точка существует В
ПРИНЦИПЕ, но НЕ АКТИВИРОВАНА в этом ките. Находки:
 1. Раннер хуков вызывает PreToolUse ОБЩЕЙ функцией для ЛЮБОГО
    tool_name (не только Task/Agent) -- строка из бандла: "let u=
    {...kf(o,void 0,n),hook_event_name:\"PreToolUse\",tool_name:e,
    tool_input:r,tool_use_id:t};yield*vP({hookInput:u,toolUseID:t,
    matchQuery:e,...})" внутри generator'а, логирующего
    "executePreToolHooks called for tool: ${e}" -- `e` (matchQuery)
    -- ЛЮБОЕ имя тула, включая continuation-инструмент; settings.json
    "matcher" фильтрует, КАКИЕ команды сработают на этом событии, не
    само событие.
 2. Continuation-инструмент этого харнесса -- отдельный, РЕАЛЬНО
    зарегистрированный тул с ИМЕНЕМ "SendMessage" (найдено буквально
    в бандле: `eh="SendMessage"`; `Mi({name:eh,searchHint:"send
    messages to agent teammates",...})` -- полноценное определение
    тула, не служебная строка). Это означает: hook-раннер способен
    вызвать PreToolUse СОБЫТИЕ для вызова SendMessage ТОЧНО ТАК ЖЕ,
    как для Task/Agent -- механизм общий.
 3. НЕ ПРОВЕРЕНО живым смоком (вне роли builder этой задачи, D-0037 --
    потребовало бы реального SendMessage-вызова к живому агенту под
    активным хуком): (а) СОВПАДАЕТ ли реальный tool_name полезной
    нагрузки PreToolUse для SendMessage буквально со строкой
    "SendMessage" (по аналогии с tool_input.subagent_type для
    Task/Agent, задокументированной в tools/dispatch_gate.py t-150
    смоком) -- ожидаемо да (тот же паттерн `name:eh`, что у любого
    другого зарегистрированного тула), но НЕ подтверждено живым
    payload'ом; (б) какая часть tool_input у SendMessage несёт
    целевой agent_id/session -- нужна для того, чтобы снимок мог бы
    (если бы это было в scope) обновляться на continuation ТОЖЕ.
 ВЫВОД для этого коммита: семантика расхождения задокументирована
 (выше), хук-точка для устранения слепоты ЕСТЬ (matcher можно
 расширить на "Task|SendMessage" в settings.json), но её АКТИВАЦИЯ
 -- новый enforcement-effect на .claude/settings.json -- вне
 объявленного scope пункта 4 (спека просит "документировать
 семантику + проверить эмпирикой, есть ли хук-точка", не "включить
 её") и, будь она включена, подпадает под D-0069/CLAUDE.md правило 2
 (самоактивирующийся enforcement-файл размещает Lead при приёмке, не
 builder) -- решение и размещение оставлены координатору.

П2 (батч мелочей после калибровки №6, D-0081) -- ГРОМКИЙ fail-open
=====================================================================
Мотив (находка калибровки №6): 2026-08-04 в 16:32 был критик-диспатч
(subagent_type=critic), но .claude/critic_snapshot.json НЕ обновился
(стоял с 07-30 01:49) -- причина проглочена голым `except Exception:
return 0` в main(): следа отказа не было ВООБЩЕ, "снимок не взят"
неотличимо от "снимок просто старый". Проба 08-05 (400 читаемых
файлов) причину не воспроизвела -- кандидат: файл дерева, залоченный
внешним приложением, в момент обхода.

FAIL-OPEN СОХРАНЁН (хук по-прежнему НИКОГДА не роняет диспатч ни при
каком исключении, exit код всегда 0 -- инвариант, пин-тест обязателен
у стороны, кому дан owns на test_critic_snapshot.py, см. отчёт
билдера), но отказ теперь ВИДИМ ДВУМЯ независимыми каналами:
 1. Диагностическая строка в stderr (`critic_snapshot.py: FAILED to
    take snapshot (<ExceptionType>: <msg>)`) -- см. _write_failure_
    snapshot().
 2. Запись факта отказа В САМ .claude/critic_snapshot.json -- поля
    `error`/`error_ts` (БЕЗ обычных ts/tree_hash/files_count/
    skipped_files -- отказ ЗАМЕЩАЕТ обычный снимок, не смешивается с
    ним: смешанный документ с ОБОИМИ шейпами усложнил бы грейдеру
    различение "снимок взят, но с оговоркой" от "снимок НЕ взят
    вовсе" -- собственное решение, задокументировано, не угадано
    молча), чтобы "снимок не взят" отличалось от "снимок старый"
    (старый снимок несёт РЕАЛЬНЫЙ ts предыдущего успешного вызова;
    отказный несёт error_ts момента отказа -- две разные, не
    смешиваемые формы документа).
Если и запись файла отказа невозможна (напр. каталог .claude/ тоже
недоступен для записи) -- ТОЛЬКО stderr, exit 0 всё равно (see
main()/_write_failure_snapshot(): внутренний try/except вокруг
самой записи файла отказа -- belt-and-suspenders поверх
belt-and-suspenders, тот же принцип, что уже был в этом файле).

ПЕРЕСДАЧА (не-блокер (б), критик, 2026-08-05): отказный документ
раньше ЗАТИРАЛ предыдущий успешный снимок целиком -- будущий грейдер
терял ЛЮБУЮ базовую линию сверки "финал не ревьюился" (устаревший, но
РЕАЛЬНЫЙ снимок был бы полезнее полного отсутствия tree_hash). ФИКС:
если файл на snap уже содержал НАСТОЯЩИЙ успешный снимок (несёт ключ
"tree_hash", не сам был отказом), его ts/tree_hash копируются в
отказный документ ОТДЕЛЬНЫМИ ключами `prev_ts`/`prev_tree_hash` --
_read_prior_snapshot_fields(). Инвариант "отказ не выглядит валидным
снимком" сохранён: отказный документ НЕ несёт ключ "tree_hash" сам
(только "prev_tree_hash" -- явно другое имя), грейдер по-прежнему
однозначно отличает "снимок взят" от "снимок НЕ взят, но был
предыдущий -- вот его данные".

ДВЕ РАЗЛИЧНЫЕ ТОЧКИ ОТКАЗА, ОБЕ ПОКРЫТЫ: main() теперь оборачивает
(а) обход дерева (compute_tree_hash()) и (б) запись снимка
(snap.write_text) в ОТДЕЛЬНЫЕ try/except -- ЛЮБАЯ из двух веток ведёт
к _write_failure_snapshot(), но семантически они разные ("не смогли
посчитать хэш" vs "посчитали, но не смогли записать") -- докстринг
_write_failure_snapshot() и main() называют обе явно.

НЕЧИТАЕМЫЙ ОДИН ФАЙЛ ДЕРЕВА -- РЕШЕНИЕ (спека явно оставляла выбор
"пропускать со счётчиком или падать", задокументировано, не угадано
молча): compute_tree_hash() ПРОПУСКАЕТ файл, чей read_bytes() кинул
исключение (PermissionError/OSError/что угодно), инкрементируя
НОВЫЙ счётчик `skipped_files` -- НЕ роняет обход целиком. Обоснование:
снимок дерева БЕЗ одного нечитаемого файла (напр. залоченного внешним
приложением, как в живой находке 08-04) полезнее ПОЛНОГО отказа
снимка из-за ЕДИНСТВЕННОГО файла -- тот же fail-open принцип, что уже
пронизывает весь этот модуль (снимок -- измеритель, не гейт).
compute_tree_hash() теперь возвращает ТРОЙКУ (tree_hash, files_count,
skipped_files) вместо прежней пары -- единственный вызывающий код в
этом репозитории (main() этого же файла; grep подтвердил -- 0 других
мест в репо импортируют compute_tree_hash) обновлён вместе; twin
toolkit/tools/critic_snapshot.py НЕ тронут (мораторий D-0074, порт --
отдельным батчем). `skipped_files` пишется в НОРМАЛЬНЫЙ (успешный)
снимок тоже (даже когда 0) -- та же дисциплина "не молчаливый 0", что
Rule #1 требует для денежных величин в других механизмах этого кита,
применённая здесь к телеметрии обхода.

DoD/owns ЭТОЙ ПРАВКИ: манифест исходного батча НЕ давал owns на
tools/test_critic_snapshot.py (файла с тестами critic_snapshot.py в
репозитории не было ВООБЩЕ) -- возвращено координатору явным частичным
статусом при первой сдаче. Пересдача (2026-08-05) явно расширила owns
на "их тесты" -- tools/test_critic_snapshot.py заведён этим коммитом
(см. отчёт билдера)."""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

EXCLUDED_DIR_NAMES = {".claude", ".git", "__pycache__", ".pytest_cache"}
EXCLUDED_REL_FILES = {Path("logs") / "routing-log.jsonl"}
SNAPSHOT_REL_PATH = Path(".claude") / "critic_snapshot.json"


def compute_tree_hash(root: Path) -> tuple[str, int, int]:
    """Возвращает (tree_hash, files_count, skipped_files). Нечитаемый
    ОДИН файл (read_bytes() кидает исключение) НЕ роняет весь обход --
    пропускается, инкрементируя skipped_files -- см. докстринг модуля,
    "П2", "НЕЧИТАЕМЫЙ ОДИН ФАЙЛ ДЕРЕВА"."""
    entries = []
    skipped_files = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
            continue
        if rel in EXCLUDED_REL_FILES:
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            skipped_files += 1
            continue
        entries.append(f"{rel.as_posix()}:{digest}")
    tree = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return tree, len(entries), skipped_files


def _read_prior_snapshot_fields(snap: Path) -> dict:
    """Пересдача (не-блокер (б), критик): читает ts/tree_hash ПРЕДЫДУЩЕГО
    документа снимка (если он существует, парсится И это НАСТОЯЩИЙ
    успешный снимок -- несёт ключ "tree_hash", не сам был отказом) --
    fail-open: отсутствие файла / битый JSON / отказный документ без
    tree_hash -- {} (баз prev_* полей в результирующем отказе, ничего
    не выдумываем). Не бросает исключений наружу."""
    try:
        prev = json.loads(snap.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(prev, dict) or "tree_hash" not in prev:
        return {}
    return {"prev_ts": prev.get("ts"), "prev_tree_hash": prev.get("tree_hash")}


def _write_failure_snapshot(snap: Path, exc: Exception) -> None:
    """П2 (батч после калибровки №6): fail-open остаётся (хук никогда
    не роняет диспатч), но отказ теперь ГРОМКИЙ -- см. докстринг
    модуля, "П2". Отказный документ ЗАМЕЩАЕТ обычный (не несёт
    ts/tree_hash/files_count/skipped_files) -- две формы документа не
    смешиваются -- инвариант "отказ не выглядит валидным снимком"
    сохранён БУКВАЛЬНО (нет ключа "tree_hash" в отказном документе).

    Пересдача (не-блокер (б), критик): ДО этой правки отказный документ
    ЗАТИРАЛ последний успешный снимок целиком -- будущий грейдер терял
    ЛЮБУЮ базовую линию сверки "финал не ревьюился" (прежнее поведение
    без этого хука оставляло УСТАРЕВШИЙ, но РЕАЛЬНЫЙ снимок с настоящим
    tree_hash). ФИКС: если СУЩЕСТВУЮЩИЙ файл на snap -- настоящий
    успешный снимок (несёт "tree_hash"), его ts/tree_hash копируются в
    отказный документ ОТДЕЛЬНЫМИ ключами `prev_ts`/`prev_tree_hash`
    (шейпы НЕ смешиваются -- отказный документ по-прежнему не несёт
    "tree_hash" САМ, только "prev_tree_hash", различимый ключ) -- см.
    _read_prior_snapshot_fields(). Если запись файла отказа тоже
    невозможна -- только stderr (исключение здесь проглатывается молча,
    НАМЕРЕННО -- это последний рубеж fail-open, сообщение уже ушло в
    stderr выше)."""
    diag = f"critic_snapshot.py: FAILED to take snapshot ({type(exc).__name__}: {exc})"
    print(diag, file=sys.stderr)
    try:
        doc = {
            "error": f"{type(exc).__name__}: {exc}",
            "error_ts": datetime.now().isoformat(),
        }
        doc.update(_read_prior_snapshot_fields(snap))
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(
            json.dumps(doc, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass  # только stderr -- см. докстринг модуля, "П2"


def main() -> int:
    # STAGING_HQ (t-159 п.7-style): байтовое stdin-чтение, тот же
    # класс правки, что t-159 п.3/dispatch_gate.py -- применено
    # единообразно ко всем staging_hq хукам, не только к тому, что
    # спека называла явно.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0  # fail open: не наш формат -- не мешаем

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool_name not in ("Task", "Agent"):
        return 0
    if tool_input.get("subagent_type") != "critic":
        return 0

    cwd = Path(payload.get("cwd") or ".")
    snap = cwd / SNAPSHOT_REL_PATH

    # П2: две РАЗЛИЧНЫЕ точки отказа -- обход дерева и запись снимка --
    # см. докстринг модуля, "ДВЕ РАЗЛИЧНЫЕ ТОЧКИ ОТКАЗА".
    try:
        tree_hash, files_count, skipped_files = compute_tree_hash(cwd)
    except Exception as exc:
        _write_failure_snapshot(snap, exc)
        return 0

    try:
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(
            json.dumps(
                {
                    "ts": datetime.now().isoformat(),
                    "tree_hash": tree_hash,
                    "files_count": files_count,
                    "skipped_files": skipped_files,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        _write_failure_snapshot(snap, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
