"""owns_verify.py -- детерминированный CLI приёмочного шага (D-0095):
post-batch сверка ФАКТИЧЕСКИ тронутых путей против декларации owns
(манифест контекста, D-0073) -- слой 2 защиты от коллизий параллельных
диспатчей (вместе с tools/owns_gate.py, PreToolUse-хуком слоя 1).

ИНТЕРФЕЙС:
  python tools/owns_verify.py --owns "<path1;path2;glob3>" \
      [--paths "<t1;t2;...>"] [--paths-file FILE] [--git-diff REF]

 --owns    ОБЯЗАТЕЛЕН -- декларация владения, токены разделены `;`
           (также принимаются `,`/перевод строки -- та же общая
           функция split_and_clean_tokens, что и tools/owns_gate.py,
           просто более терпимая к форме ввода, чем документированный
           интерфейс требует буквально; вреда от этого нет).
 --paths   явный список фактически тронутых путей, та же форма токенов.
 --paths-file FILE
           путь построчно (по одному пути на строку, пустые строки
           пропускаются).
 --git-diff REF
           пути ИЗМЕНЁННЫХ tracked-файлов (`git diff --name-only REF`)
           ОБЪЕДИНЁННЫЕ с untracked-файлами (`git ls-files --others
           --exclude-standard`) -- ПЕРЕПИСАНО в attempt 2 по вердикту
           критика (B3): `git diff` НЕ ВИДИТ untracked-файлы вовсе (это
           не diff, это отдельный список путей), а НОВЫЕ файлы --
           самый частый продукт пишущего builder-диспатча (D-0073
           owns) -- без второго источника owns_verify систематически
           слеп на главный случай. Корень репозитория резолвится ОДИН
           РАЗ через `git rev-parse --show-toplevel` (subprocess
           списком, без shell=True); КАЖДЫЙ путь из ОБОИХ git-вызовов
           (оба возвращают пути ОТНОСИТЕЛЬНО корня репо) резолвится в
           АБСОЛЮТНЫЙ (root / rel) ДО сверки с --owns -- --owns несёт
           абсолютные пути по норме R11 кита, сверка относительного с
           абсолютным никогда бы не совпала. Оба git-вызова наследуют
           cwd вызвавшего процесса (правило 9 CLAUDE.md кита -- обычная
           командная гигиена и так требует запуска из корня); отказ
           `git rev-parse` (не git-репозиторий) -- та же ошибка
           вызова exit 2, что и сбой `git diff`/`git ls-files`.
 Источники --paths/--paths-file/--git-diff -- АДДИТИВНЫ: если указано
 несколько, все их пути объединяются в один список для сверки
 (собственное инженерное решение -- спека явно не описывает поведение
 при одновременной подаче нескольких источников, задокументировано,
 не угадано молча). Ни один источник не указан (или --paths -- пустая
 строка/omitted) -- список путей пуст -- легальный случай (спека DoD:
 "Пустой --paths при валидном вызове -> OWNS OK 0").

ОБЩИЙ КОД С tools/owns_gate.py: normalize_path/paths_overlap/
split_and_clean_tokens ИМПОРТИРУЮТСЯ отсюда из owns_gate.py (одна
реализация сверки на двоих, направление задокументировано в
докстринге tools/owns_gate.py, "ОБЩИЙ КОД С tools/owns_verify.py").
Семантика overlap -- ТА ЖЕ, что у owns_gate.py (нормализация
lower+`/`, вложенность по границе сегмента, fnmatch при глобе).

ВЫХОД:
 - каждый путь из --paths/--paths-file/--git-diff, НЕ пересекающийся ни
   с ОДНИМ токеном декларации --owns -> строка "OUT-OF-OWNS: <path>" в
   stdout; если найден хотя бы один такой путь -- exit 1 (после того,
   как ВСЕ строки-нарушители напечатаны, не выходит на первом же).
 - все пути внутри декларации (либо путей 0) -> "OWNS OK: N paths
   within M declared" (N -- число проверенных путей, M -- число
   токенов декларации owns) и exit 0.
 - ОШИБКА ВЫЗОВА (не вердикт!) -- отсутствие --owns (либо пустая
   строка -- трактуется как отсутствие декларации, собственное решение,
   задокументировано: owns целиком пустой для пишущего диспатча
   бессмысленен по норме R11 CLAUDE.md кита) ИЛИ сбой `git diff`
   (ненулевой код возврата либо git недоступен вовсе, напр.
   FileNotFoundError) -> сообщение в stderr, exit 2 -- ОТЛИЧИМ от
   вердикта exit 1 (нарушение) намеренно, той же экономикой, что
   remaining tools кита различают "решение" и "сбой вызова"."""

import argparse
import subprocess
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from tools.owns_gate import paths_overlap, split_and_clean_tokens  # package-style
except ImportError:
    from owns_gate import paths_overlap, split_and_clean_tokens  # sibling-module fallback

__all__ = ["verify", "main"]


def _read_paths_file(path_str: str) -> list:
    raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _git_repo_root() -> Path:
    """`git rev-parse --show-toplevel` -- корень репозитория, ОДИН РАЗ
    на вызов --git-diff (B3). Отказ (не git-репо, git недоступен) --
    ошибка вызова, ПОДНИМАЕТСЯ как RuntimeError -- ловится в main() и
    превращается в exit 2 (см. докстринг модуля)."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git rev-parse --show-toplevel failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return Path(result.stdout.strip())


def _run_git_name_only(args: list) -> list:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_diff_paths(ref: str) -> list:
    """Объединяет `git diff --name-only REF` (изменённые tracked) И
    `git ls-files --others --exclude-standard` (untracked) -- ПОЧЕМУ
    ОБА ИСТОЧНИКА: см. докстринг модуля, "--git-diff REF". Оба
    возвращают пути ОТНОСИТЕЛЬНО корня репо -- каждый резолвится в
    АБСОЛЮТНЫЙ (root / rel) ПЕРЕД возвратом, дедуп с сохранением
    порядка (diff -- сначала, untracked -- следом)."""
    root = _git_repo_root()
    diff_rel = _run_git_name_only(["git", "diff", "--name-only", ref])
    untracked_rel = _run_git_name_only(["git", "ls-files", "--others", "--exclude-standard"])

    seen = []
    for rel in diff_rel + untracked_rel:
        abs_path = str((root / rel).resolve())
        if abs_path not in seen:
            seen.append(abs_path)
    return seen


def _collect_paths(args) -> list:
    paths = []
    if args.paths:
        paths.extend(split_and_clean_tokens(args.paths))
    if args.paths_file:
        paths.extend(_read_paths_file(args.paths_file))
    if args.git_diff:
        paths.extend(_git_diff_paths(args.git_diff))
    return paths


def verify(owns_decl: list, paths: list) -> list:
    """Возвращает список путей из paths, НЕ пересекающихся ни с одним
    токеном owns_decl (порядок сохраняется, как в paths)."""
    violations = []
    for p in paths:
        if not any(paths_overlap(p, o) for o in owns_decl):
            violations.append(p)
    return violations


def _reconfigure_stdout_utf8():
    """cp1251/узкая консоль (командная гигиена) -- см.
    tools/hygiene_gate.py._reconfigure_stdout_utf8; этот CLI печатает
    вызывающе-заданные пути (OUT-OF-OWNS-строки), чьи символы узкая
    консольная кодовая страница может не суметь закодировать (порт
    кит-фикса)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main(argv=None) -> int:
    _reconfigure_stdout_utf8()
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--owns")
    parser.add_argument("--paths", default="")
    parser.add_argument("--paths-file")
    parser.add_argument("--git-diff")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.owns:
        sys.stderr.write("owns_verify: --owns is required\n")
        return 2

    owns_decl = split_and_clean_tokens(args.owns)

    try:
        paths = _collect_paths(args)
    except Exception as exc:
        sys.stderr.write(f"owns_verify: {exc}\n")
        return 2

    violations = verify(owns_decl, paths)
    for v in violations:
        print(f"OUT-OF-OWNS: {v}")

    if violations:
        return 1

    print(f"OWNS OK: {len(paths)} paths within {len(owns_decl)} declared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
