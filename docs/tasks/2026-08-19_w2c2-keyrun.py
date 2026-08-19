#!/usr/bin/env python3
"""W2c-2 key-runner (R11.l): checks every S2 key of
docs/tasks/2026-08-19_w2c-keys.md against its own address.

Fold contract (_fold_whitespace, D-0054/08-19 finding t-496):
  {space, tab, CR, LF}+ -> single space; '|' is NOT folded.

Usage:
  python w2c2_key_runner.py            # normal run
  python w2c2_key_runner.py --drop-a ID   # negative control: pretend
                                            key ID (class A/A') is absent
  python w2c2_key_runner.py --drop-b ID   # negative control: pretend
                                            key ID (class B) is absent
Exit code 0 = all keys found at their own address; 1 = failure
(including an empty key list, and any positional mismatch).
"""
import re
import sys
import argparse

ROOT = None  # set below


def _fold_whitespace(s: str) -> str:
    # {space, tab, CR, LF}+ -> one space; '|' left alone.
    return re.sub(r"[ \t\r\n]+", " ", s)


# id, class, text, address (relative path; None => checked against protocol)
KEYS = [
    # D1
    ("d1-1", "A", "Греп-попадание на имя гейта бывает ТРЁХ родов", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-2", "A", "(2) НАЗВАН ПРЕДМЕТОМ ПРОВЕРКИ ЕГО ОТКАЗА/ЖИВОСТИ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-3", "A", "(3) НАЗВАН КАК ИНСТРУМЕНТ ЧУЖОЙ ПРОВЕРКИ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-4", "A", "РЕЖИМ ОТКАЗА, НЕ ФОРМА УПОМИНАНИЯ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-5", "A", "не отличает «нарушений не было» от «гейт мёртв, записей нет вообще»", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-6", "A", "САМИ подпункты (б)/(в)/(г) ниже и тексты других чеков, ПЕРЕЧИТАННЫЕ ЗАНОВО", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-7", "A", "резолюция по данным — законная форма опознания предмета", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d1-8", "C", "ПОКРЫТЫ (молчание детектируется)", "docs/RULE_COVERAGE.md"),
    ("d1-9", "C", "ПОКРЫТЫ ЧАСТИЧНО", "docs/RULE_COVERAGE.md"),
    ("d1-10", "C", "НЕ ПОКРЫТЫ (детектора отказа/живости нет нигде в протоколе)", "docs/RULE_COVERAGE.md"),
    ("d1-11", "A'", "прогон пересчитывает категорию (2) по факту текста", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    # D2
    ("d2-1", "A", "сверить состав `.claude/settings.json` ПО ФАКТУ ФАЙЛА НА МОМЕНТ ПРОГОНА", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d2-2", "A", "расхождение перечисления протокола с фактом = находка САМА ПО СЕБЕ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d2-3", "A", "состав сходится", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d2-4", "A", "правка скрипта БЕЗ правки settings.json проходит мимо осевого блока", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d2-5", "A", "СВЯЗЬ С F-56 (невод механизмов)", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d2-6", "P", "tools/negative_lint.py", ".claude/settings.json"),
    # D3
    ("d3-1", "A", "блокирующий класс «журнал мимо Edit/Write» permissionDecision НЕСЁТ ПО ЗАМЫСЛУ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d3-2", "A", "его ИСЧЕЗНОВЕНИЕ есть регресс", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d3-3", "A", "все ОСТАЛЬНЫЕ классы хука — warn-only", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d3-4", "A", "появление permissionDecision у любого из них = регресс в обратную сторону", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d3-5", "B", "была верна для v1 t-177 и ПРОТУХЛА после VG-5 2026-07-23", "PROCESS/CALIBRATION_HISTORY.md"),
    # D4
    ("d4-1", "A", "Живость hygiene_gate сверяется ЧЕКОМ 25 ПО ЕГО ФАКТИЧЕСКОМУ СКОУПУ НА МОМЕНТ ПРОГОНА", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d4-2", "A", "скоуп расширяется решением по evidence, D-0063, и тогда же расширяется эта сверка", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d4-3", "A", "находки аудита класса, ВХОДЯЩЕГО в текущий скоуп хука, при ПУСТЫХ warn-строках", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d4-4", "A", "Правило сверки при любой редакции скоупа одно", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d4-5", "A'", "v1-триггер t-177 ловил только класс", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d4-6", "B", "на 2026-07-19 (калибровка №3, по чтению кода)", "PROCESS/CALIBRATION_HISTORY.md"),
    # D5'
    ("d5-1", "A", "КРИТЕРИЙ ЗАСЧИТЫВАНИЯ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d5-2", "A", "засчитывается (полностью или частично", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d5-R", "R", "не может служить своим же положительным контролем", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    # D14
    ("d14-1", "A'", "База контрфакта = привязка", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d14-2", "A'", "разрыв базы помечается в notes", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d14-3", "A", "вопрос контрфакта звучит «а если бы это делал Lead», и имя модели в нём не константа", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d14-4", "A", "по ценам ПРИВЯЗКИ `roles.lead` НА МОМЕНТ ОКНА", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d14-5", "B", "всё ещё держит `FABLE_MODEL` константой", "PROCESS/CALIBRATION_HISTORY.md"),
    # D15
    ("d15-1", "A'", "с НАПРАВЛЕНИЕМ ошибки", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d15-2", "A'", "известные разрывы — PROCESS/CALIBRATION_HISTORY.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d15-3", "A", "(в) цена за принятую единицу делегированной работы", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d15-4", "A", "(г) API-контур: учётный итог по traffic_kind + real-доля", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d15-5", "B", "№6 шла в окне 07-29T18:42..08-05T12:34", "PROCESS/CALIBRATION_HISTORY.md"),
    ("d15-6", "B", "брутто-экономия №7 ЗАВЫШЕНА, а не занижена", "PROCESS/CALIBRATION_HISTORY.md"),
    # D16
    ("d16-1", "A", "Секция отчёта «ПРОПУЩЕННЫЕ ОКНА»", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-2", "A", "обязана быть пустой ЛИБО объяснённой в notes", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-3", "A", "аудит СОСТОЯНИЯ НА СТАРТЕ прогона", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-4", "A", "отсутствие чисел в notes `calibrated` видно следующему прогону и оператору (F-32)", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-5", "A", "Калибровка ЗАПИСЫВАЕТ и свой собственный прогон в реестр run_units", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-6", "A", "Это ЕДИНСТВЕННАЯ новая обязанность", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d16-7", "B", "формулировка ДО этой правки утверждала", "PROCESS/CALIBRATION_HISTORY.md"),
    # D9/D9b
    ("d9-1", "A", "Целостность task_id (D-0060): дублей task_id между несвязанными задачами нет", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-2", "A", "residual-детектор TOCTOU-окна кодового гарда AO3 log_append.py", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-3", "A", "ts-честность (F-29): выборочная сверка ts событий окна с внешними часами", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-4", "A", "расхождение порядка часов или немонотонность внутри сессии = нарушение", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-5", "A", "Промоция в код — ts-sanity в объёме B1-валидатора (очередь)", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-6", "A'", "известные поправки счёта — PROCESS/CALIBRATION_HISTORY.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d9-7", "B", "Известный дубль — t-008", "PROCESS/CALIBRATION_HISTORY.md"),
    ("d9-8", "B", "во всех счётах чеков 3/13 идёт как ДВЕ задачи", "PROCESS/CALIBRATION_HISTORY.md"),
    ("d9b-1", "B", "события t-023..t-026", "PROCESS/CALIBRATION_HISTORY.md"),
    ("d9b-2", "B", "брать реальные времена из notes defect_found", "PROCESS/CALIBRATION_HISTORY.md"),
    # D17
    ("d17-1", "A", "ГРАНИЦА ДЕГРАДАЦИИ — ПРИВЯЗКА, А НЕ ИМЯ МОДЕЛИ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-2", "A", "Lead-активность на модели НИЖЕ `roles.lead` ТОГО деплоя, чей журнал читается", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-3", "A", "при спорной строке — привязка на МОМЕНТ СОБЫТИЯ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-4", "A", "Модель, РАВНАЯ привязке, — штатный полный Lead, не деградация", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-5", "A", "классифицируется вслух как ИСТОРИЯ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-6", "A", "Хоть одно попадание класса КРИТЕРИЙ", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d17-7", "B", "Lead-активность на модели ниже Fable вне заявленного окна", "PROCESS/CALIBRATION_HISTORY.md"),
    # D18
    ("d18-1", "A'", "для окон ДО 2026-08-16", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d18-2", "A", "(iv) КЛАУЗУЛА НЕЗАВИСИМОГО КОНТЕКСТА (D-0099", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d18-3", "A", "Основания (iii)/(iv) читаются по привязке ТОГО деплоя, чей журнал читается, а не по имени модели", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d18-4", "A", "Такая строка законна БЕЗ basis, и требование basis к ней = ложное срабатывание", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d18-5", "A", "Льгота «critic: skipped» легальна только у принимающего выше исполнителя", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d18-6", "B", "она отстала от D-0087 (2026-07-21) и D-0099 (2026-08-04)", "PROCESS/CALIBRATION_HISTORY.md"),
    # D19
    ("d19-1", "A", "каждый hq-drift и каждый файл штаба без кит-твина ЛЕГАЛЕН только если его класс явно помечен «кухня»", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d19-2", "A", "прочий разрыв = НЕДОПОСТАВКА, находка калибровки", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d19-3", "A", "обкатка у добровольцев", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d19-4", "B", "отменён словом оператора 2026-08-10", "PROCESS/CALIBRATION_HISTORY.md"),
    # D20
    ("d20-1", "A", "Стоимостной кроссовер эскалаций (Update Rule 4 таблицы, исполняемая", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d20-2", "A", "фактическая полная стоимость всех попыток", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d20-3", "A", "Систематический минус по категории (дешёвый ярус с ретраями дороже) = evidence для правки границы делегирования", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d20-4", "A", "Пустое окно (0 эскалаций) — явно", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"),
    ("d20-5", "B", "правило 6 ССЫЛАЛОСЬ на калибровку, но исполняемого чека не было, класс F-15", "PROCESS/CALIBRATION_HISTORY.md"),
]


def load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return _fold_whitespace(f.read())


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--drop-a", default=None, help="negative control: drop this A/A'-class key id")
    ap.add_argument("--drop-b", default=None, help="negative control: drop this B-class key id")
    args = ap.parse_args()
    ROOT = args.root

    if not KEYS:
        print("EMPTY KEY LIST -> FAIL (pустой список ключей = скрипт обязан упасть)")
        sys.exit(1)

    cache = {}

    def get(path):
        full = ROOT.rstrip("/\\") + "/" + path
        if full not in cache:
            cache[full] = load(full)
        return cache[full]

    ok = True
    rows = []
    for kid, klass, text, addr in KEYS:
        folded = _fold_whitespace(text)
        content = get(addr)

        # negative-control simulation: pretend the key text was struck
        # from its own carrier by never finding it there.
        simulate_absent = (args.drop_a == kid and klass in ("A", "A'")) or (
            args.drop_b == kid and klass == "B"
        )

        if simulate_absent:
            found_own = False
        else:
            found_own = folded in content

        if klass == "R":
            # must be ABSENT from its address (retirement)
            verdict = not found_own
        else:
            verdict = found_own

        # cross-check: verify it's not accidentally satisfied by a
        # DIFFERENT carrier only (i.e. address mismatch) -- for A/A'/B/C/P
        # classes we already pinned the single correct address above,
        # so a positive hit there is definitionally "at its own address".
        rows.append((kid, klass, addr, verdict))
        if not verdict:
            ok = False

    for kid, klass, addr, verdict in rows:
        print(f"{'OK ' if verdict else 'FAIL'}  {kid:8s} [{klass:2s}]  {addr}")

    print()
    print("RESULT:", "ALL KEYS OK" if ok else "FAILURE (see FAIL rows above)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
