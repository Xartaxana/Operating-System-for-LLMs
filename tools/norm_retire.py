"""Детерминированный чекер инвариантов ретирования (Phase 5, W1).

Норма — docs/DECISIONS_FULL.md / docs/FINDINGS.md шапки (блок
«Ретирование (Phase 5, W1)») + DECISIONS.md шапка (инлайн-суффикс
статуса индексной строки). Спека:
docs/tasks/2026-08-18_w1-retirement-spec.md.

Два ретируемых слоя (пары канон<->архив):
    (docs/DECISIONS_FULL.md, docs/DECISIONS_ARCHIVE.md, "## D-NNNN")
    (docs/FINDINGS.md,       docs/FINDINGS_ARCHIVE.md,   "## F-NN")

Стаб (форма A2 спеки): тело секции в каноне НАЧИНАЕТСЯ маркером
"**РЕТИРОВАНО <YYYY-MM-DD>.**" (единственный машинный признак стаба),
несёт ровно одну строку-указатель "секция `## <ID>`" вместе с путём
архивного дома своей пары, тело <= 4 непустых строк и <= 400 байт
UTF-8, не содержит "**Класс.**"/"**Класс**" (D-0100 не ослаблен).
Архивный дом несёт секцию `## <ID>` VERBATIM (заголовок повторяет
канонический дословно) либо ровно строку
"**РЕАНИМИРОВАНО <YYYY-MM-DD> -> <канон-путь>.**" (тело вернулось в
канон, стаб исчез).

Секция-граница (обе пары): от строки заголовка `## <ID>` до
СЛЕДУЮЩЕЙ строки, начинающейся с "## ", хвостовые пустые строки
среза срезаны -- тот же контракт, что extract_decision_section()
tools/escape_check.py (тело для D-NNNN действительно ХЕШИРУЕТСЯ
через import escape_check в CLI-ветке --hash-canon/--hash-archive
ниже; для F-NN -- локальная зеркальная реализация того же контракта,
extract_finding_section()/finding_section_sha256()). Внутренний
enumerate-проход --check (_iter_sections) реализует ТОТ ЖЕ алгоритм
для обеих пар единообразно (кросс-проверка равенства с
escape_check -- tools/test_norm_retire.py).

CLI:
    python tools/norm_retire.py --check
        Прогоняет все восемь инвариантов (I1..I8) на живом дереве,
        печатает построчно "I<N> OK" или "I<N> FAIL" (плюс диагностику
        под провалившимися строками с отступом). Exit 0 если все OK,
        иначе 1.

    python tools/norm_retire.py --hash-canon <ID>
    python tools/norm_retire.py --hash-archive <ID>
        Печатает sha256 hex дайджест секции <ID> (заголовок+тело) в
        каноническом файле своей пары (--hash-canon) либо в архивном
        доме своей пары (--hash-archive). <ID> вида D-NNNN или F-NN;
        неопознанная форма, отсутствующий файл, отсутствующая или
        задвоенная секция -- exit 1 с ASCII-диагностикой на stderr.

Любой другой вызов -- usage-ошибка, exit 2, ничего не проверяется
(fail-closed, тот же принцип, что у escape_check.py).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

# python tools/norm_retire.py вставляет SCRIPT_DIR в sys.path[0]
# автоматически (интерпретатор); при импорте модулем из
# tools/test_norm_retire.py тот же путь уже стоит в sys.path через
# pytest rootdir-инсерцию (тот же паттерн, что tools/test_escape_check.py
# "import escape_check as ec" и tools/conftest.py "import spend_model") --
# ручной sys.path.insert не нужен ни в одном из двух режимов запуска.
import escape_check  # для D-NNNN: --hash-canon/--hash-archive контракт


# ---------------------------------------------------------------------
# Пары канон<->архив.
# ---------------------------------------------------------------------


class Pair:
    def __init__(self, name, canon_rel, archive_rel, header_re, id_re):
        self.name = name
        self.canon_rel = canon_rel
        self.archive_rel = archive_rel
        self.header_re = header_re
        self.id_re = id_re


DECISIONS_PAIR = Pair(
    "decisions",
    "docs/DECISIONS_FULL.md",
    "docs/DECISIONS_ARCHIVE.md",
    re.compile(r"^## (D-\d{4})(?![A-Za-z0-9])"),
    re.compile(r"^D-\d{4}$"),
)
FINDINGS_PAIR = Pair(
    "findings",
    "docs/FINDINGS.md",
    "docs/FINDINGS_ARCHIVE.md",
    re.compile(r"^## (F-\d+)(?![A-Za-z0-9])"),
    re.compile(r"^F-\d+$"),
)
PAIRS = (DECISIONS_PAIR, FINDINGS_PAIR)

DECISIONS_INDEX_REL = "DECISIONS.md"
ALLOWLIST_REL = "tools/escape_allowlist.json"


# ---------------------------------------------------------------------
# Нормализация / извлечение секций (общий контракт для обеих пар).
# ---------------------------------------------------------------------


def _normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _iter_sections(text, header_re):
    """Возвращает список (id, body) для КАЖДОГО top-level `## <ID>`
    заголовка, совпадающего с header_re, в порядке появления в тексте.
    body -- всё после строки заголовка до следующей строки "## " (или
    конца текста), хвостовые пустые строки среза срезаны. Дубликаты ID
    не схлопываются -- каждое вхождение попадает в список отдельно
    (нужно для I6)."""
    normalized = _normalize_newlines(text)
    lines = normalized.split("\n")
    starts = []
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m:
            starts.append((i, m.group(1)))
    sections = []
    for start, sid in starts:
        end = start + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        body_lines = lines[start + 1 : end]
        while body_lines and body_lines[-1] == "":
            body_lines.pop()
        sections.append((sid, "\n".join(body_lines)))
    return sections


def extract_finding_section(text, finding_id):
    """Зеркало escape_check.extract_decision_section() для F-NN секций
    docs/FINDINGS.md -- тот же контракт границы (A4 спеки): от строки
    заголовка до следующей "## ", хвостовые пустые срезаны. Возвращает
    (section_text, status); section_text incl. строку заголовка."""
    normalized = _normalize_newlines(text)
    pattern = re.compile(r"^## " + re.escape(finding_id) + r"(?![A-Za-z0-9])")
    lines = normalized.split("\n")
    matches = [i for i, line in enumerate(lines) if pattern.match(line)]

    if not matches:
        return None, "not_found"
    if len(matches) > 1:
        return None, "duplicate"

    start = matches[0]
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1

    section_lines = lines[start:end]
    while section_lines and section_lines[-1] == "":
        section_lines.pop()

    return "\n".join(section_lines), "ok"


def finding_section_sha256(text, finding_id):
    import hashlib

    section_text, status = extract_finding_section(text, finding_id)
    if status != "ok":
        return None, status
    digest = hashlib.sha256(section_text.encode("utf-8")).hexdigest()
    return digest, "ok"


def read_utf8(path):
    """Читает path как UTF-8 текст. Возвращает (text, None) либо
    (None, error_str) -- никогда не бросает (fail-closed, A8.4 "не-UTF-8
    архив -- FAIL явным текстом")."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return None, "cannot read file %s: %s" % (path, exc)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, "file %s is not valid UTF-8: %s" % (path, exc)
    return text, None


# ---------------------------------------------------------------------
# Форма стаба -- маркеры.
# ---------------------------------------------------------------------

RETIRED_RE = re.compile(r"^\*\*РЕТИРОВАНО (\d{4}-\d{2}-\d{2})\.\*\*")
REANIMATED_RE = re.compile(r"^\*\*РЕАНИМИРОВАНО \d{4}-\d{2}-\d{2} -> .+\.\*\*$")
KLASS_RE = re.compile(r"\*\*Класс\.?\*\*")


def _nonempty_lines(body):
    return [l for l in body.split("\n") if l.strip() != ""]


def is_stub(body):
    """Единственный машинный признак стаба (A2.2): первая непустая
    строка тела совпадает с маркером РЕТИРОВАНО."""
    for line in body.split("\n"):
        if line.strip() == "":
            continue
        return bool(RETIRED_RE.match(line.lstrip()))
    return False


# ---------------------------------------------------------------------
# I1 -- стаб => архив.
# ---------------------------------------------------------------------


def check_I1(pair, canon_sections, archive_exists, archive_sections):
    failures = []
    archive_id_counts = Counter(sid for sid, _ in archive_sections)
    own_path = pair.archive_rel
    other_path = (FINDINGS_PAIR if pair is DECISIONS_PAIR else DECISIONS_PAIR).archive_rel

    for sid, body in canon_sections:
        if not is_stub(body):
            continue

        nonempty = _nonempty_lines(body)
        if len(nonempty) > 4:
            failures.append(
                "I1 %s: тело > 4 непустых строк (%d)" % (sid, len(nonempty))
            )
        body_bytes = len(body.encode("utf-8"))
        if body_bytes > 400:
            failures.append(
                "I1 %s: тело > 400 байт UTF-8 (%d)" % (sid, body_bytes)
            )

        token = "секция `## %s`" % sid
        lines = body.split("\n")
        own_pointer_lines = [l for l in lines if token in l and own_path in l]
        any_token_lines = [l for l in lines if token in l]
        wrong_pair_lines = [
            l for l in lines if token in l and own_path not in l and other_path in l
        ]
        if len(own_pointer_lines) != 1:
            if wrong_pair_lines:
                failures.append(
                    "I1 %s: указатель ссылается на архив чужой пары" % sid
                )
            elif any_token_lines:
                failures.append(
                    "I1 %s: указатель некорректен или задвоен (%d совпадений)"
                    % (sid, len(any_token_lines))
                )
            else:
                failures.append("I1 %s: нет строки-указателя на архив" % sid)

        # Примечание: "тело -- одна лишь строка-реанимация" (A4 I1) не
        # кодируется отдельной веткой здесь -- она СТРУКТУРНО
        # недостижима при данном is_stub(): первая непустая строка
        # стаба обязана совпасть с RETIRED_RE (маркер РЕТИРОВАНО),
        # который никогда не совпадёт с REANIMATED_RE (другое слово) --
        # тело, начинающееся строкой-реанимацией, вообще не признаётся
        # стабом (is_stub -> False) и до этой ветки I1 не доходит.

        if archive_exists:
            cnt = archive_id_counts.get(sid, 0)
            if cnt != 1:
                failures.append(
                    "I1 %s: дом несёт %d секций %s, ожидалась 1" % (sid, cnt, sid)
                )
        # archive_exists is False -> deferred to I8 (стаб указывает на
        # несуществующий дом целиком), не дублируем диагностику здесь.

    return failures


# ---------------------------------------------------------------------
# I2 -- архив => канон (гейт фазы (в)).
# ---------------------------------------------------------------------


def check_I2(canon_sections, archive_sections):
    failures = []
    canon_by_id = {}
    for sid, body in canon_sections:
        canon_by_id.setdefault(sid, []).append(body)

    for sid, abody in archive_sections:
        canon_bodies = canon_by_id.get(sid)
        if not canon_bodies:
            failures.append("I2 %s: архивная секция без канонного заголовка" % sid)
            continue
        cbody = canon_bodies[0]

        a_nonempty = _nonempty_lines(abody)
        is_empty = len(a_nonempty) == 0
        is_reanim_only = len(a_nonempty) == 1 and bool(
            REANIMATED_RE.match(a_nonempty[0].strip())
        )

        if is_empty:
            failures.append(
                "I2 %s: заголовок архива без тела и без реанимации" % sid
            )
            continue

        if is_reanim_only:
            if not cbody.strip():
                failures.append(
                    "I2 %s: форма не распознана (канон пуст при реанимации)" % sid
                )
            elif is_stub(cbody):
                failures.append(
                    "I2 %s: реанимация ожидает полный текст в каноне, "
                    "канон остался стабом" % sid
                )
        else:
            if not cbody.strip():
                failures.append(
                    "I2 %s: форма не распознана (пустое тело секции в каноне)" % sid
                )
            elif not is_stub(cbody):
                failures.append(
                    "I2 %s: архив несёт тело, но канон не стаб "
                    "(тело и там и там)" % sid
                )

    return failures


# ---------------------------------------------------------------------
# I3 -- паритет решений (только D-пара).
# ---------------------------------------------------------------------


def check_I3(decisions_full_text, decisions_index_text):
    failures = []
    d_ids = {
        m.group(1)
        for m in re.finditer(
            r"(?m)^## (D-\d{4})(?![A-Za-z0-9])", _normalize_newlines(decisions_full_text)
        )
    }
    idx_ids = {
        m.group(1)
        for m in re.finditer(
            r"(?m)^- (D-\d{4})\b", _normalize_newlines(decisions_index_text)
        )
    }
    missing_in_index = sorted(d_ids - idx_ids)
    missing_in_full = sorted(idx_ids - d_ids)
    if missing_in_index:
        failures.append("I3: в индексе нет строк для %s" % missing_in_index)
    if missing_in_full:
        failures.append("I3: в DECISIONS_FULL нет секций для %s" % missing_in_full)
    return failures


# ---------------------------------------------------------------------
# I4 -- индекс несёт статус (только D-пара).
# ---------------------------------------------------------------------


def check_I4(canon_sections_d, decisions_index_text):
    failures = []
    idx_lines = _normalize_newlines(decisions_index_text).split("\n")
    idx_by_id = {}
    for line in idx_lines:
        m = re.match(r"^- (D-\d{4})\b", line)
        if m:
            idx_by_id[m.group(1)] = line

    for sid, body in canon_sections_d:
        if not is_stub(body):
            continue
        line = idx_by_id.get(sid)
        if line is None:
            failures.append("I4 %s: нет строки индекса" % sid)
        elif "РЕТИРОВАНО" not in line:
            failures.append("I4 %s: строка индекса без токена РЕТИРОВАНО" % sid)
    return failures


# ---------------------------------------------------------------------
# I5 -- пины неприкосновенны (только D-пара).
# ---------------------------------------------------------------------


def check_I5(canon_sections_d, allowlist_path):
    failures = []
    try:
        with open(allowlist_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return failures  # нет валидного allowlist -> ничего не запинено

    pinned = {
        e.get("decision_id") for e in data.get("entries", []) if e.get("decision_id")
    }
    stub_ids = {sid for sid, body in canon_sections_d if is_stub(body)}
    hit = sorted(pinned & stub_ids)
    if hit:
        failures.append("I5: запинненные решения стабированы: %s" % hit)
    return failures


# ---------------------------------------------------------------------
# I6 -- уникальность заголовков (обе пары, канон и архив).
# ---------------------------------------------------------------------


def check_I6(label, canon_sections, archive_sections):
    failures = []
    for where, sections in (("канон", canon_sections), ("архив", archive_sections)):
        counts = Counter(sid for sid, _ in sections)
        for sid, c in sorted(counts.items()):
            if c > 1:
                failures.append(
                    "I6 %s/%s: %s встречается %d раз" % (label, where, sid, c)
                )
    return failures


# ---------------------------------------------------------------------
# I7 -- D-0100 не ослаблен (обе пары).
# ---------------------------------------------------------------------


def check_I7(canon_sections):
    failures = []
    for sid, body in canon_sections:
        if is_stub(body) and KLASS_RE.search(body):
            failures.append("I7 %s: стаб несёт **Класс.**" % sid)
    return failures


# ---------------------------------------------------------------------
# I8 -- пустые/отсутствующие миры (обе пары).
# ---------------------------------------------------------------------


def check_I8(canon_sections, archive_exists, archive_sections):
    failures = []
    stubs = [sid for sid, body in canon_sections if is_stub(body)]
    if not stubs:
        return failures
    if not archive_exists:
        for sid in stubs:
            failures.append(
                "I8 %s: стаб указывает на несуществующий дом" % sid
            )
    elif len(archive_sections) == 0:
        for sid in stubs:
            failures.append(
                "I8 %s: стаб указывает на несуществующий дом (архив пуст)" % sid
            )
    return failures


# ---------------------------------------------------------------------
# --check оркестрация.
# ---------------------------------------------------------------------


def run_check(repo_root=None):
    """Возвращает (ok: bool, lines: list[str]) -- lines пригодны для
    прямой печати построчно (контракт CLI: "I<N> OK/FAIL" на
    инвариант, диагностика с отступом под провалившимися)."""
    repo_root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)

    failures = {"I%d" % n: [] for n in range(1, 9)}
    utf8_errors = []

    pair_data = {}
    for pair in PAIRS:
        canon_path = repo_root / pair.canon_rel
        archive_path = repo_root / pair.archive_rel

        canon_text, err = read_utf8(canon_path)
        if err is not None:
            utf8_errors.append("канон %s: %s" % (pair.canon_rel, err))
            pair_data[pair.name] = ([], False, [])
            continue

        archive_exists = archive_path.is_file()
        archive_sections = []
        if archive_exists:
            archive_text, aerr = read_utf8(archive_path)
            if aerr is not None:
                utf8_errors.append("архив %s: %s" % (pair.archive_rel, aerr))
                failures["I1"].append(
                    "I1 %s: архивный файл не читается как UTF-8 -- %s"
                    % (pair.name, aerr)
                )
            else:
                archive_sections = _iter_sections(archive_text, pair.header_re)

        canon_sections = _iter_sections(canon_text, pair.header_re)
        pair_data[pair.name] = (canon_sections, archive_exists, archive_sections)

        failures["I1"] += check_I1(pair, canon_sections, archive_exists, archive_sections)
        failures["I2"] += check_I2(canon_sections, archive_sections)
        failures["I6"] += check_I6(pair.name, canon_sections, archive_sections)
        failures["I7"] += check_I7(canon_sections)
        failures["I8"] += check_I8(canon_sections, archive_exists, archive_sections)

    d_canon_sections, _, _ = pair_data["decisions"]
    decisions_full_text, err1 = read_utf8(repo_root / DECISIONS_PAIR.canon_rel)
    decisions_index_text, err2 = read_utf8(repo_root / DECISIONS_INDEX_REL)
    if err1 is None and err2 is None:
        failures["I3"] += check_I3(decisions_full_text, decisions_index_text)
        failures["I4"] += check_I4(d_canon_sections, decisions_index_text)
    else:
        for e in (err1, err2):
            if e:
                utf8_errors.append(e)
        failures["I3"].append("I3: не удалось прочитать индекс/канон")
        failures["I4"].append("I4: не удалось прочитать индекс/канон")

    failures["I5"] += check_I5(d_canon_sections, repo_root / ALLOWLIST_REL)

    ok = all(len(v) == 0 for v in failures.values())

    lines = []
    for msg in utf8_errors:
        lines.append("UTF8-ERROR: %s" % msg)
    for n in range(1, 9):
        key = "I%d" % n
        status = "OK" if not failures[key] else "FAIL"
        lines.append("%s %s" % (key, status))
        for msg in failures[key]:
            lines.append("    %s" % msg)

    return ok, lines


# ---------------------------------------------------------------------
# --hash-canon / --hash-archive.
# ---------------------------------------------------------------------


def _pair_for_id(norm_id):
    for pair in PAIRS:
        if pair.id_re.match(norm_id):
            return pair
    return None


def _section_sha256_for_id(text, norm_id, pair):
    if pair is DECISIONS_PAIR:
        return escape_check.section_sha256(text, norm_id)
    return finding_section_sha256(text, norm_id)


def _cli_hash(norm_id, use_canon, repo_root):
    pair = _pair_for_id(norm_id)
    if pair is None:
        sys.stderr.write(
            "NORM RETIRE HASH FAILED: unrecognized id form %r (expected D-NNNN or F-NN)\n"
            % norm_id
        )
        return 1

    rel = pair.canon_rel if use_canon else pair.archive_rel
    path = Path(repo_root) / rel
    text, err = read_utf8(path)
    if text is None:
        sys.stderr.write("NORM RETIRE HASH FAILED: %s\n" % err)
        return 1

    digest, status = _section_sha256_for_id(text, norm_id, pair)
    if status == "not_found":
        sys.stderr.write(
            "NORM RETIRE HASH FAILED: section %s not found in %s\n" % (norm_id, rel)
        )
        return 1
    if status == "duplicate":
        sys.stderr.write(
            "NORM RETIRE HASH FAILED: section %s duplicated in %s\n" % (norm_id, rel)
        )
        return 1

    sys.stdout.write("%s\n" % digest)
    return 0


# ---------------------------------------------------------------------
# main.
# ---------------------------------------------------------------------


def main(argv):
    args = argv[1:]
    repo_root = REPO_ROOT

    if len(args) == 1 and args[0] == "--check":
        ok, lines = run_check(repo_root)
        for line in lines:
            print(line)
        return 0 if ok else 1

    if len(args) == 2 and args[0] == "--hash-canon":
        return _cli_hash(args[1], use_canon=True, repo_root=repo_root)

    if len(args) == 2 and args[0] == "--hash-archive":
        return _cli_hash(args[1], use_canon=False, repo_root=repo_root)

    sys.stderr.write(
        "usage: norm_retire.py --check | --hash-canon <ID> | --hash-archive <ID>\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
