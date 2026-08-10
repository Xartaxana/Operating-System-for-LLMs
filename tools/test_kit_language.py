"""test_kit_language.py -- машинный детектор «ноль нарративной кириллицы
в отгружаемом ките» (решение Ф11б батча v0.8.0 -- норма БЕЗ детектора
остаётся желанием, D-0065 п.(в)). Живёт в ШТАБНОЙ кухне tools/ (гоняется
каждым каноном `python -m pytest tools/ gateway/ -q`), СКАНИРУЕТ
toolkit/ -- staging-снимок отгружаемого кита (docs/SIBLING_MAP.md,
"toolkit/ -- staging ядра (политика EN, роли, скиллы, PROCESS, tools,
gateway-kit)"). Кит НЕ правится этим файлом (чужие owns) -- только
читается.

ТРИАЖ-КРИТЕРИЙ (спека, буквально): НАРРАТИВНАЯ кириллица (проза,
комментарии, докстринги-повествование) в ките запрещена; ФУНКЦИОНАЛЬНАЯ
легальна -- детекционные литералы (образец: tools/negative_lint.py's
NEG_MARKERS_RU/CONTROL_MARKERS_RU, toolkit/tools/dispatch_gate.py:224-280
DOD_MARKERS_RE/WRITE_INDICATORS_RE/MANIFEST_GIVEN_RE, все прочитаны перед
реализацией -- то есть кириллица ВНУТРИ regex-паттерна или строкового
маркера-литерала), тестовые RU-фикстуры (payload'ы вида toolkit/tools/
test_tier_echo.py's "клод-опус"/"фейбл"), докстринг-цитаты этих же
литералов.

ФАЙЛОВЫЕ КЛАССЫ (три независимых правила, DoD пп.1-3):

 1. toolkit/**/*.md -- СТРОГИЙ ноль кириллицы, весь файл целиком (нет
    понятия "комментарий"/"докстринг" в markdown -- вся прозы = нарратив
    по определению этого документного класса).
 2. toolkit/**/*.{json,jsonl,yaml,yml} -- строгий ноль, тем же
    основанием (шаблоны/конфиги релизного кита -- EN, синтетические
    corpus-шаблоны -- EN payload'ы).
 3. toolkit/**/*.py -- через tokenize (см. НИЖЕ "КОМПРОМИСС ДОКСТРИНГОВ"
    за обоснование, почему докстринги идут через ast, а не через голый
    STRING-токен tokenize):
      - КОММЕНТАРИИ (# ...) -- строгий ноль БЕЗ ИСКЛЮЧЕНИЙ, даже когда
        комментарий дословно ЦИТИРУЕТ функциональный маркер (спека
        разрешает цитаты только в докстрингах, не в комментариях --
        живой пример был найден первым прогоном этого детектора (18
        комментарий-нарушений): toolkit/tools/dispatch_gate.py:229-230
        комментировал regex-корень по-русски внутри английского
        комментария -- нарушение по буквальному тексту спеки; все 18,
        включая последний остаток в toolkit/tools/test_wiring_check.py
        (чужой owns параллельной ветки), почищены диспатчами t-412/
        t-413 -- живой корпус сейчас несёт ноль таких нарушений (см.
        test_no_cyrillic_in_python_comments ниже, без xfail)).
      - строковые ЛИТЕРАЛЫ (не докстринги) -- разрешены целиком, без
        разбора содержимого (фикстуры/маркеры).
      - ДОКСТРИНГИ -- см. компромисс ниже.

КОМПРОМИСС ДОКСТРИНГОВ (спека явно требует назвать и задокументировать
реализованный выбор, DoD п.3): надёжно отличить "докстринг цитирует
функциональный маркер" от "докстринг несёт нарративную прозу по-русски"
БЕЗ семантического понимания текста НЕВОЗМОЖНО чисто синтаксически --
оба вида кириллицы физически неотличимы как токены. РЕАЛИЗОВАННЫЙ
КОМПРОМИСС: докстринги (module/class/def/async def -- первый Expr-
statement тела, найденный через ast, НЕ через позиционную эвристику
tokenize, потому что ast даёт точную привязку "это действительно
docstring-позиция" без ложных совпадений на произвольных строковых
statement'ах в середине функции) разрешены ЦЕЛИКОМ -- их основное тело
НЕ проверяется вовсе. Взамен -- ОТДЕЛЬНЫЙ репорт-ассерт (см.
test_no_cyrillic_in_docstring_first_line ниже): кириллица в ПЕРВОЙ
СТРОКЕ докстринга (docstring_text.split("\n", 1)[0]) -- отдельное
нарушение своего вида "docstring-first-line". Обоснование компромисса
(спека, буквально): "нарратив начинается с первой строки; цитаты
маркеров в первой строке не живут".

ЭТО ДОПУЩЕНИЕ СПЕКИ ЭМПИРИЧЕСКИ ОПРОВЕРГАЛОСЬ НА ЖИВОМ КОРПУСЕ ДО t-412
(правило 3 роли -- проверяй, не предполагай): toolkit/tools/
test_dispatch_gate.py нёс РОВНО ДВЕ докстроки, чьи первые строки были
легитимными цитатами литералов "продано"/"дано"
(test_manifest_given_word_boundary_prodano_false_positive_fixed,
строка 495) и "Дано:"/"дано --" (test_manifest_given_real_forms_
unaffected_by_word_boundary, строка 506) -- обе НАЧИНАЛИСЬ цитатой на
первой строке, вопреки допущению спеки. Это был ЛЕГАЛЬНЫЙ по смыслу
текст (функциональная цитата), но report-ассерт всё равно его ловил --
ИЗВЕСТНОЕ ограничение выбранного компромисса, задокументированное
здесь явно, не молчаливое: он консервативен в СТОРОНУ ложных
срабатываний на цитаты первой строки, а не в сторону пропуска
нарратива (test_docstring_narrative_cyrillic_not_on_first_line_is_not_
flagged_known_limitation ниже пином фиксирует и обратный класс --
нарратив НЕ на первой строке этим ассертом не ловится вовсе). Выбор
осознанный: пропуск нарратива хуже ложного срабатывания на цитату
(цитату координатор отличит на глаз за секунду по репорту
file:line+фрагмент; пропущенный нарратив -- нет). t-412 переписал
первые строки обеих докстрок на EN-описание (RU-цитаты сдвинуты ниже
первой строки) и снял xfail с test_no_cyrillic_in_docstring_first_line
-- живой пример этого допущения больше не наблюдается на текущем
корпусе; сам компромисс (и его известное ограничение) остаётся в силе
на будущее.

ИСКЛЮЧЁННЫЕ ДИРЕКТОРИИ (собственное инженерное решение, не угадано
молча): __pycache__/ и .pytest_cache/ исключены из скана целиком --
обе явно в toolkit/.gitignore ("__pycache__/", "*.pyc", ".pytest_cache/"
-- прочитано перед реализацией), то есть НЕ являются частью
закоммиченного/отгружаемого кита вовсе, а локальным build-мусором
текущей машины; сканировать их -- шум, не относящийся к "отгружаемому
киту" по смыслу задачи.

КОДИРОВКА (fail-open на бинарные/не-UTF8 файлы, DoD "краевые"):
файл читается БАЙТАМИ и декодируется utf-8 СТРОГО (errors="strict", не
"replace" -- инженерное решение: "replace" подставил бы U+FFFD молча и
мог бы скрыть/исказить реальную кириллицу под соседними битыми байтами;
детектору лучше явно ПРОПУСТИТЬ нечитаемый файл и перечислить его в
списке skipped, чем анализировать испорченный текст). UnicodeDecodeError
-> файл пропускается, добавляется в перечень skipped (список, не
молчание) -- см. test_binary_file_skipped_not_crashed/test_non_utf8_
bytes_file_skipped_not_crashed за живую проверку этого пути.

TOKENIZE/AST-ОШИБКА СИНТАКСИСА (DoD "краевые"): файл .py, не проходящий
tokenize.generate_tokens ИЛИ ast.parse, репортится в список unreadable
(один файл -- одна запись, дедуп между tokenize- и ast-ошибкой одного и
того же файла) -- сам скан ПРОДОЛЖАЕТСЯ по остальным файлам (try/except
Exception ВОКРУГ каждого файла по отдельности, не вокруг всего цикла) --
см. test_python_syntax_error_reported_unreadable_not_crashing.

ПУСТОЙ/ОТСУТСТВУЮЩИЙ toolkit/ (DoD "краевые", форк без кита): live-тесты
(сканирующие настоящий toolkit/ этого репозитория) несут
@_LIVE_SKIP -- pytest.mark.skipif на _toolkit_has_scan_targets(), явный
skip-reason в отчёте pytest, НЕ silent pass и не крах; логика этой
функции покрыта отдельными юнит-тестами на синтетических tmp_path
(test_toolkit_has_scan_targets_*), не зависящими от реального toolkit/.

ALLOWLIST (DoD п.4): ALLOWLIST -- кортеж (relpath, reason); СЕЙЧАС ПУСТ
(test_allowlist_is_currently_empty пином фиксирует этот факт). Каждая
будущая запись обязана нести НЕПУСТУЮ причину -- _validate_allowlist()
вызывается на уровне модуля сразу после определения константы, так что
запись без причины валит КОЛЛЕКЦИЮ теста немедленно и громко, а не
тихо (test_allowlist_entries_require_non_empty_reason_validated_at_import
фиксирует это поведение на синтетическом примере, не трогая реальную
константу).

СООБЩЕНИЕ О НАРУШЕНИИ (DoD п.5, формат буквально из спеки): file:line +
усечённый фрагмент (MAX_FRAGMENT_LEN=160, многоточие "…" при усечении --
число символов, как и PREVIEW_MAX_LEN в tools/negative_lint.py, СВОЁ
инженерное решение, не угадано молча -- граничные тесты см.
test_truncate_exact_boundary_not_truncated/test_truncate_over_
boundary_truncated_with_ellipsis, правило 6а) + подсказка "narrative
Cyrillic is a release-quality violation; functional literals belong in
string literals, not comments" (дословно из спеки).

ФОРМА ФАЙЛА (прецеденты, прочитаны целиком перед реализацией):
tools/test_findings_form.py -- парсер-детектор формы, самодостаточный
модуль без репозиторных импортов, живой прогон по реальному
корпусу (@pytest.mark.parametrize по живым записям) -- тот же принцип
здесь применён к живому toolkit/, только без parametrize (единый
агрегированный ассерт на список нарушений -- список короче и нагляднее
одним блоком, чем 200+ отдельных parametrize-узлов по каждому файлу
кита); toolkit/tools/test_*.py -- style-прецедент tmp_path-фикстур для
негативных/позитивных контролей (см. tools/test_negative_lint.py's
tmp_path CLI-тесты, тот же паттерн использован ниже).

НЕГАТИВНЫЙ КОНТРОЛЬ САМОГО ДЕТЕКТОРА (командная гигиена, "норма
вечнозелёных скриптов"): test_negative_control_* ниже -- нарочно
испорченные СИНТЕТИЧЕСКИЕ tmp_path-фикстуры (НЕ живые файлы кита,
никакой порчи боевого артефакта, правило 10) с преднамеренной
нарративной кириллицей в каждом из проверяемых мест (markdown,
config, комментарий, докстринг-первая-строка) -- без них детектор
неотличим от неработающего (всегда молчащего) скрипта."""

from __future__ import annotations

import ast
import functools
import io
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLKIT_ROOT = REPO_ROOT / "toolkit"

EXCLUDED_DIR_NAMES = {"__pycache__", ".pytest_cache"}

CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")

MAX_FRAGMENT_LEN = 160

HINT = (
    "narrative Cyrillic is a release-quality violation; functional "
    "literals belong in string literals, not comments"
)

ALL_SCAN_PATTERNS = ("*.md", "*.json", "*.jsonl", "*.yaml", "*.yml", "*.py")

# Явный per-file allowlist будущих законных исключений (DoD п.4) --
# сейчас пуст; каждая запись -- (relpath относительно REPO_ROOT в
# posix-форме, непустая строка-причина).
ALLOWLIST: tuple[tuple[str, str], ...] = ()


def _validate_allowlist(allowlist: tuple) -> None:
    """Каждая запись ALLOWLIST обязана нести непустую причину -- вызвано
    на уровне модуля сразу после определения константы (см. ниже), так
    что нарушение валит коллекцию теста немедленно и громко."""
    for path, reason in allowlist:
        assert isinstance(path, str) and path, f"allowlist entry has empty path: {path!r}"
        assert isinstance(reason, str) and reason.strip(), (
            f"allowlist entry {path!r} has an empty reason -- every exception needs one"
        )


_validate_allowlist(ALLOWLIST)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    col: int
    fragment: str
    kind: str  # "markdown" | "config" | "comment" | "docstring-first-line"


@dataclass
class PyFileScan:
    comment_violations: list
    docstring_violations: list
    unreadable: "str | None"
    skipped_binary: bool


def _truncate(s: str, max_len: int = MAX_FRAGMENT_LEN) -> str:
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def format_violation(v: Violation) -> str:
    return f"{v.path}:{v.line}: [{v.kind}] {_truncate(v.fragment.strip())} -- {HINT}"


def filter_allowlisted(violations: list, allowlist: tuple) -> list:
    """Отбрасывает нарушения, чей path целиком (весь файл) присутствует
    в allowlist -- принимает allowlist ЯВНЫМ аргументом (не читает
    модульную константу напрямую), так что юнит-тест может проверить
    логику фильтрации синтетическим примером, не трогая ALLOWLIST."""
    allowed_paths = {path for path, _reason in allowlist}
    return [v for v in violations if v.path not in allowed_paths]


def _relpath(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve().parent).as_posix()


def _iter_files(root: Path, pattern: str):
    if not root.is_dir():
        return
    for p in sorted(root.rglob(pattern)):
        if not p.is_file():
            continue
        try:
            rel_parts = p.relative_to(root).parts
        except ValueError:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in rel_parts[:-1]):
            continue
        yield p


def _read_utf8_strict(path: Path) -> "tuple[str | None, bool]":
    """(text, skipped) -- skipped=True на OSError/не-UTF8 (см. модульный
    докстринг, "КОДИРОВКА")."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None, True
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        return None, True


def _scan_one_plain_text_file(path: Path, rel: str, kind: str) -> "tuple[list, bool]":
    text, skipped = _read_utf8_strict(path)
    if skipped:
        return [], True
    violations = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = CYRILLIC_RE.search(line)
        if m:
            violations.append(Violation(rel, lineno, m.start() + 1, line, kind))
    return violations, False


def scan_plain_text_files(root: Path, patterns, kind: str) -> "tuple[list, list]":
    violations = []
    skipped = []
    for pattern in patterns:
        for path in _iter_files(root, pattern):
            rel = _relpath(path, root)
            file_violations, is_skipped = _scan_one_plain_text_file(path, rel, kind)
            if is_skipped:
                skipped.append(rel)
            else:
                violations.extend(file_violations)
    return violations, skipped


def _scan_one_python_file(path: Path, rel: str) -> PyFileScan:
    text, skipped = _read_utf8_strict(path)
    if skipped:
        return PyFileScan([], [], None, True)

    comment_violations = []
    docstring_violations = []
    unreadable = None

    tokens = None
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except Exception as exc:  # tokenize.TokenizeError/IndentationError/SyntaxError/ValueError -- см. докстринг "TOKENIZE/AST-ОШИБКА"
        unreadable = f"{rel}: tokenize error: {exc}"

    if tokens is not None:
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                m = CYRILLIC_RE.search(tok.string)
                if m:
                    comment_violations.append(
                        Violation(rel, tok.start[0], tok.start[1] + m.start() + 1, tok.string, "comment")
                    )

    try:
        tree = ast.parse(text, filename=rel)
    except Exception as exc:
        if unreadable is None:
            unreadable = f"{rel}: ast parse error: {exc}"
        return PyFileScan(comment_violations, [], unreadable, False)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(getattr(first, "value", None), ast.Constant)
                and isinstance(first.value.value, str)
            ):
                doc_text = first.value.value
                first_line = doc_text.split("\n", 1)[0]
                m = CYRILLIC_RE.search(first_line)
                if m:
                    docstring_violations.append(
                        Violation(rel, first.lineno, m.start() + 1, first_line, "docstring-first-line")
                    )

    return PyFileScan(comment_violations, docstring_violations, unreadable, False)


def scan_python_files(root: Path) -> "tuple[list, list, list, list]":
    """(comment_violations, docstring_violations, unreadable, skipped)."""
    comment_v = []
    doc_v = []
    unreadable = []
    skipped = []
    for path in _iter_files(root, "*.py"):
        rel = _relpath(path, root)
        result = _scan_one_python_file(path, rel)
        if result.skipped_binary:
            skipped.append(rel)
            continue
        if result.unreadable:
            unreadable.append(result.unreadable)
        comment_v.extend(result.comment_violations)
        doc_v.extend(result.docstring_violations)
    return comment_v, doc_v, unreadable, skipped


def _toolkit_has_scan_targets(root: Path) -> bool:
    """True, если root существует и содержит хотя бы один файл любого
    из сканируемых паттернов -- используется, чтобы live-тесты явно
    skip'ались (не молча проходили и не падали) на форке без toolkit/
    или с пустым toolkit/ (DoD "краевые")."""
    if not root.is_dir():
        return False
    for pattern in ALL_SCAN_PATTERNS:
        if next(root.rglob(pattern), None) is not None:
            return True
    return False


_LIVE_SKIP_REASON = (
    f"toolkit/ absent or empty in this checkout ({TOOLKIT_ROOT}) -- "
    "nothing to scan (fork/edge case)"
)
_LIVE_SKIP = pytest.mark.skipif(
    not _toolkit_has_scan_targets(TOOLKIT_ROOT), reason=_LIVE_SKIP_REASON
)


@functools.lru_cache(maxsize=1)
def _cached_python_scan():
    return scan_python_files(TOOLKIT_ROOT)


# ---------------------------------------------------------------------
# Live-тесты по настоящему toolkit/ этого репозитория.
# ---------------------------------------------------------------------


@_LIVE_SKIP
def test_no_cyrillic_in_markdown_files():
    violations, _skipped = scan_plain_text_files(TOOLKIT_ROOT, ["*.md"], "markdown")
    violations = filter_allowlisted(violations, ALLOWLIST)
    assert not violations, "\n".join(format_violation(v) for v in violations)


@_LIVE_SKIP
def test_no_cyrillic_in_config_files():
    violations, _skipped = scan_plain_text_files(
        TOOLKIT_ROOT, ["*.json", "*.jsonl", "*.yaml", "*.yml"], "config"
    )
    violations = filter_allowlisted(violations, ALLOWLIST)
    assert not violations, "\n".join(format_violation(v) for v in violations)


# ИСТОРИЯ (DoD п.5 честно предполагал возможность красного прогона на
# живом ките -- "тест тогда честно красный, приложи и список, и
# вывод"; механизм xfail-с-причиной, tools/dod_track.py's
# determine_outcome(), t-262/t-275, санкционировал именно этот случай):
# первый прогон этого детектора нашёл 18 комментарий-нарушений в ките.
# t-412 (диспатч этого файла) почистил 16 из них; оставшиеся 2
# (toolkit/tools/test_wiring_check.py:810,853) были в owns параллельной
# ветки, xfail(strict=True) держал прогон честно зелёным до её
# схождения. t-413 (эта правка): параллельная ветка почистила
# остаток -- живой корпус toolkit/ несёт НОЛЬ комментарий-кириллицы
# (проверено прогоном ниже, включая test_negative_control_comment_
# scanner_catches_deliberate_cyrillic как позитивный/негативный
# контроль самого детектора). xfail снят -- никакого известного
# исключения больше нет, тест -- боевой ассерт без смягчений.


@_LIVE_SKIP
def test_no_cyrillic_in_python_comments():
    comment_v, _doc_v, _unreadable, _skipped = _cached_python_scan()
    comment_v = filter_allowlisted(comment_v, ALLOWLIST)
    assert not comment_v, "\n".join(format_violation(v) for v in comment_v)


@_LIVE_SKIP
def test_no_cyrillic_in_docstring_first_line():
    _comment_v, doc_v, _unreadable, _skipped = _cached_python_scan()
    doc_v = filter_allowlisted(doc_v, ALLOWLIST)
    assert not doc_v, "\n".join(format_violation(v) for v in doc_v)


@_LIVE_SKIP
def test_no_unreadable_python_files_in_kit():
    _comment_v, _doc_v, unreadable, _skipped = _cached_python_scan()
    assert not unreadable, "\n".join(unreadable)


# ---------------------------------------------------------------------
# _toolkit_has_scan_targets -- синтетические границы (DoD "краевые").
# ---------------------------------------------------------------------


def test_toolkit_has_scan_targets_false_for_missing_dir(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert _toolkit_has_scan_targets(missing) is False


def test_toolkit_has_scan_targets_false_for_empty_dir(tmp_path):
    empty = tmp_path / "empty_toolkit"
    empty.mkdir()
    assert _toolkit_has_scan_targets(empty) is False


def test_toolkit_has_scan_targets_true_when_file_present(tmp_path):
    root = tmp_path / "toolkit"
    root.mkdir()
    (root / "a.md").write_text("hello", encoding="utf-8")
    assert _toolkit_has_scan_targets(root) is True


# ---------------------------------------------------------------------
# Негативный/позитивный контроль детектора -- синтетические tmp_path
# фикстуры (см. модульный докстринг, "НЕГАТИВНЫЙ КОНТРОЛЬ").
# ---------------------------------------------------------------------


def test_negative_control_comment_scanner_catches_deliberate_cyrillic(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "# обычный русский комментарий, нарративная проза\nx = 1\n",
        encoding="utf-8",
    )
    result = _scan_one_python_file(f, "toolkit/tools/sample.py")
    assert result.skipped_binary is False
    assert result.unreadable is None
    assert len(result.comment_violations) == 1
    v = result.comment_violations[0]
    assert v.line == 1
    assert v.kind == "comment"


def test_negative_control_markdown_scanner_catches_deliberate_cyrillic(tmp_path):
    f = tmp_path / "sample.md"
    f.write_text("# Заголовок\nОбычный русский нарратив.\n", encoding="utf-8")
    violations, skipped = _scan_one_plain_text_file(f, "toolkit/sample.md", "markdown")
    assert skipped is False
    assert len(violations) == 2


def test_negative_control_config_scanner_catches_deliberate_cyrillic(tmp_path):
    f = tmp_path / "sample.json"
    f.write_text('{"note": "русский текст"}', encoding="utf-8")
    violations, skipped = _scan_one_plain_text_file(f, "toolkit/sample.json", "config")
    assert skipped is False
    assert len(violations) == 1


def test_negative_control_docstring_first_line_scanner_catches_deliberate_narrative(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        '"""Обычная нарративная докстрока по-русски, не цитата маркера."""\nx = 1\n',
        encoding="utf-8",
    )
    result = _scan_one_python_file(f, "toolkit/tools/sample.py")
    assert result.unreadable is None
    assert len(result.docstring_violations) == 1
    assert result.docstring_violations[0].kind == "docstring-first-line"


def test_string_literal_cyrillic_is_legal_not_flagged(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        'NEG_MARKERS_RU = ["не найден", "отсутств"]\n'
        'x = "команда с кириллицей"  # english comment only, no cyrillic here\n',
        encoding="utf-8",
    )
    result = _scan_one_python_file(f, "toolkit/tools/sample.py")
    assert result.comment_violations == []
    assert result.docstring_violations == []
    assert result.unreadable is None


def test_docstring_narrative_cyrillic_not_on_first_line_is_not_flagged_known_limitation(tmp_path):
    # Документирует известное ограничение выбранного компромисса (см.
    # модульный докстринг): докстринг, чья ПЕРВАЯ строка чиста, а
    # ПОСЛЕДУЮЩИЕ строки несут нарративную кириллицу, легален для этого
    # детектора по построению -- докстринги разрешены ЦЕЛИКОМ, кроме
    # первой строки.
    f = tmp_path / "sample.py"
    f.write_text(
        '"""English first line, all good.\n'
        "Второй абзац нарративной кириллицы -- НЕ ловится этим детектором.\n"
        '"""\nx = 1\n',
        encoding="utf-8",
    )
    result = _scan_one_python_file(f, "toolkit/tools/sample.py")
    assert result.docstring_violations == []


# ---------------------------------------------------------------------
# Краевые случаи: бинарные/не-UTF8 файлы, синтаксически битые .py.
# ---------------------------------------------------------------------


def test_binary_file_skipped_not_crashed(tmp_path):
    f = tmp_path / "image.md"
    f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe")
    violations, skipped = _scan_one_plain_text_file(f, "toolkit/image.md", "markdown")
    assert skipped is True
    assert violations == []


def test_non_utf8_bytes_file_skipped_not_crashed(tmp_path):
    f = tmp_path / "legacy.json"
    # cp1251-байты кириллического текста -- невалидный UTF-8, должны
    # быть пропущены без исключения наружу.
    f.write_bytes("отсутствует".encode("cp1251"))
    violations, skipped = _scan_one_plain_text_file(f, "toolkit/legacy.json", "config")
    assert skipped is True
    assert violations == []


def test_python_binary_file_skipped_not_crashed(tmp_path):
    f = tmp_path / "broken_encoding.py"
    f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x01\x02\xff\xfe")
    result = _scan_one_python_file(f, "toolkit/tools/broken_encoding.py")
    assert result.skipped_binary is True
    assert result.comment_violations == []
    assert result.docstring_violations == []
    assert result.unreadable is None


def test_python_syntax_error_reported_unreadable_not_crashing(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def f(:\n    pass\n", encoding="utf-8")
    result = _scan_one_python_file(f, "toolkit/tools/broken.py")
    assert result.unreadable is not None
    assert result.comment_violations == []
    assert result.docstring_violations == []


def test_excluded_pycache_dir_is_skipped_from_python_scan(tmp_path):
    root = tmp_path / "toolkit"
    (root / "tools" / "__pycache__").mkdir(parents=True)
    (root / "tools" / "__pycache__" / "ghost.py").write_text(
        "# нарративный кириллический комментарий призрака кэша\n", encoding="utf-8"
    )
    (root / "tools" / "real.py").write_text("x = 1  # clean english comment\n", encoding="utf-8")
    comment_v, doc_v, unreadable, skipped = scan_python_files(root)
    assert comment_v == []
    assert doc_v == []
    assert unreadable == []
    assert skipped == []


def test_excluded_pytest_cache_dir_is_skipped_from_markdown_scan(tmp_path):
    root = tmp_path / "toolkit"
    cache = root / ".pytest_cache"
    cache.mkdir(parents=True)
    (cache / "README.md").write_text("Нарративный русский текст в кэше.\n", encoding="utf-8")
    violations, skipped = scan_plain_text_files(root, ["*.md"], "markdown")
    assert violations == []
    assert skipped == []


# ---------------------------------------------------------------------
# ALLOWLIST -- пуст сейчас, каждая будущая запись требует причины.
# ---------------------------------------------------------------------


def test_allowlist_is_currently_empty():
    assert ALLOWLIST == ()


def test_allowlist_entries_require_non_empty_reason_validated_at_import():
    with pytest.raises(AssertionError):
        _validate_allowlist((("toolkit/tools/some_file.py", ""),))


def test_filter_allowlisted_removes_matching_path_and_keeps_others():
    v1 = Violation("toolkit/tools/known_exception.py", 5, 1, "фрагмент", "comment")
    v2 = Violation("toolkit/tools/other.py", 5, 1, "фрагмент", "comment")
    allowlist = (
        ("toolkit/tools/known_exception.py", "documented legacy exception, see DECISIONS.md"),
    )
    remaining = filter_allowlisted([v1, v2], allowlist)
    assert remaining == [v2]


# ---------------------------------------------------------------------
# MAX_FRAGMENT_LEN -- граничные тесты (правило 6а: лимит без граничного
# теста -- незакрытый DoD).
# ---------------------------------------------------------------------


def test_truncate_exact_boundary_not_truncated():
    s = "a" * MAX_FRAGMENT_LEN
    assert _truncate(s) == s
    assert len(_truncate(s)) == MAX_FRAGMENT_LEN


def test_truncate_over_boundary_truncated_with_ellipsis():
    s = "a" * (MAX_FRAGMENT_LEN + 1)
    result = _truncate(s)
    assert result == "a" * MAX_FRAGMENT_LEN + "…"
    assert len(result) == MAX_FRAGMENT_LEN + 1


def test_truncate_one_below_boundary_not_truncated():
    s = "a" * (MAX_FRAGMENT_LEN - 1)
    assert _truncate(s) == s


# ---------------------------------------------------------------------
# format_violation -- форма сообщения (DoD п.5, буквально file:line +
# фрагмент + подсказка).
# ---------------------------------------------------------------------


def test_format_violation_contains_file_line_fragment_and_hint():
    v = Violation("toolkit/tools/x.py", 42, 3, "# нарративный фрагмент", "comment")
    msg = format_violation(v)
    assert msg.startswith("toolkit/tools/x.py:42:")
    assert "нарративный фрагмент" in msg
    assert HINT in msg
