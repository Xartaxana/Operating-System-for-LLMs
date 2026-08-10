"""Юнит-смоки tools/owns_verify.py. Покрывает DoD спеки задачи: путь в
декларации / вне декларации / вложенный / глоб, регистр и смешанные
сепараторы Windows-POSIX, пустой --paths, отсутствие --owns (exit 2),
граничный тест "ровно один нарушитель среди N" (exit 1); ПЛЮС
регресс блокера B3 (attempt 2, вердикт критика t-333) -- --git-diff
happy-path во временном git-репозитории: изменённый tracked-файл И
новый untracked-файл ОБА резолвятся в абсолютные пути от корня репо
(git rev-parse --show-toplevel) и покрываются проверкой owns."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owns_verify  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "owns_verify.py"


def _run_cli(args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        **kwargs,
    )


# ---------------------------------------------------------------------
# verify(): путь в декларации / вне / вложенный / глоб.
# ---------------------------------------------------------------------


def test_path_within_declaration_no_violation():
    violations = owns_verify.verify(["D:\\repo\\tools\\x.py"], ["D:\\repo\\tools\\x.py"])
    assert violations == []


def test_path_outside_declaration_is_violation():
    violations = owns_verify.verify(["D:\\repo\\tools\\x.py"], ["D:\\repo\\gateway\\y.py"])
    assert violations == ["D:\\repo\\gateway\\y.py"]


def test_path_nested_under_declared_directory_no_violation():
    violations = owns_verify.verify(["D:\\repo\\tools"], ["D:\\repo\\tools\\sub\\x.py"])
    assert violations == []


def test_path_matches_glob_declaration_no_violation():
    violations = owns_verify.verify(["D:\\repo\\tools\\*.py"], ["D:\\repo\\tools\\x.py"])
    assert violations == []


def test_path_not_matching_glob_declaration_is_violation():
    violations = owns_verify.verify(["D:\\repo\\tools\\*.py"], ["D:\\repo\\tools\\x.json"])
    assert violations == ["D:\\repo\\tools\\x.json"]


# ---------------------------------------------------------------------
# Регистр и смешанные сепараторы Windows-POSIX.
# ---------------------------------------------------------------------


def test_case_insensitive_match():
    violations = owns_verify.verify(["D:\\Repo\\Tools\\X.PY"], ["d:\\repo\\tools\\x.py"])
    assert violations == []


def test_mixed_windows_posix_separators_match():
    violations = owns_verify.verify(["D:/repo/tools/x.py"], ["D:\\repo\\tools\\x.py"])
    assert violations == []
    violations2 = owns_verify.verify(["D:\\repo\\tools"], ["D:/repo/tools/sub/x.py"])
    assert violations2 == []


# ---------------------------------------------------------------------
# CLI: пустой --paths при валидном вызове -> OWNS OK 0.
# ---------------------------------------------------------------------


def test_cli_empty_paths_ok(tmp_path):
    result = _run_cli(["--owns", "D:\\repo\\tools\\x.py"], cwd=str(tmp_path))
    assert result.returncode == 0
    assert "OWNS OK: 0 paths within 1 declared" in result.stdout


def test_cli_omitted_paths_ok(tmp_path):
    result = _run_cli(["--owns", "D:\\repo\\tools\\x.py;D:\\repo\\tools\\y.py"], cwd=str(tmp_path))
    assert result.returncode == 0
    assert "OWNS OK: 0 paths within 2 declared" in result.stdout


# ---------------------------------------------------------------------
# CLI: отсутствие --owns -> exit 2 (ошибка вызова, не вердикт).
# ---------------------------------------------------------------------


def test_cli_missing_owns_exits_2(tmp_path):
    result = _run_cli(["--paths", "D:\\repo\\tools\\x.py"], cwd=str(tmp_path))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--owns" in result.stderr


def test_cli_empty_owns_string_exits_2(tmp_path):
    result = _run_cli(["--owns", "", "--paths", "D:\\repo\\tools\\x.py"], cwd=str(tmp_path))
    assert result.returncode == 2


# ---------------------------------------------------------------------
# CLI: exit 1 при нарушении -- граничный тест: РОВНО один нарушитель
# среди N (правило 6а).
# ---------------------------------------------------------------------


def test_cli_exactly_one_violation_among_many_exits_1(tmp_path):
    owns = "D:\\repo\\tools\\a.py;D:\\repo\\tools\\b.py;D:\\repo\\tools\\c.py"
    paths = "D:\\repo\\tools\\a.py;D:\\repo\\tools\\b.py;D:\\repo\\gateway\\OUTSIDE.py;D:\\repo\\tools\\c.py"
    result = _run_cli(["--owns", owns, "--paths", paths], cwd=str(tmp_path))
    assert result.returncode == 1
    lines = [l for l in result.stdout.splitlines() if l.startswith("OUT-OF-OWNS:")]
    assert len(lines) == 1
    assert "OUTSIDE.py" in lines[0]


def test_cli_all_within_declaration_exits_0(tmp_path):
    owns = "D:\\repo\\tools\\a.py;D:\\repo\\tools\\b.py"
    paths = "D:\\repo\\tools\\a.py;D:\\repo\\tools\\b.py"
    result = _run_cli(["--owns", owns, "--paths", paths], cwd=str(tmp_path))
    assert result.returncode == 0
    assert "OWNS OK: 2 paths within 2 declared" in result.stdout


# ---------------------------------------------------------------------
# --paths-file и --git-diff -- сбор путей из файла и из git.
# ---------------------------------------------------------------------


def test_cli_paths_file_collects_lines(tmp_path):
    paths_file = tmp_path / "paths.txt"
    paths_file.write_text("D:\\repo\\tools\\a.py\n\nD:\\repo\\tools\\b.py\n", encoding="utf-8")
    result = _run_cli(
        ["--owns", "D:\\repo\\tools", "--paths-file", str(paths_file)], cwd=str(tmp_path)
    )
    assert result.returncode == 0
    assert "OWNS OK: 2 paths within 1 declared" in result.stdout


def test_cli_git_diff_bad_ref_exits_2(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True)
    result = _run_cli(
        ["--owns", "D:\\repo\\tools", "--git-diff", "definitely-not-a-real-ref-xyz"],
        cwd=str(tmp_path),
    )
    assert result.returncode == 2
    assert result.stdout == ""


# ---------------------------------------------------------------------
# B3: --git-diff -- корень репо + резолв в абсолютные + untracked.
# ---------------------------------------------------------------------


def _init_temp_git_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), capture_output=True, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo_dir), capture_output=True, check=True)


def test_cli_git_diff_happy_path_covers_tracked_and_untracked(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_temp_git_repo(repo)

    tracked = repo / "tracked.py"
    tracked.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(repo), capture_output=True, check=True
    )

    # изменённый tracked-файл (виден в `git diff --name-only HEAD`).
    tracked.write_text("v2\n", encoding="utf-8")
    # новый untracked-файл (НЕ виден в diff -- только в `git ls-files
    # --others`), самый частый продукт пишущего builder-диспатча.
    untracked = repo / "untracked.py"
    untracked.write_text("new\n", encoding="utf-8")

    tracked_abs = str(tracked.resolve())
    untracked_abs = str(untracked.resolve())

    result_ok = _run_cli(
        ["--owns", f"{tracked_abs};{untracked_abs}", "--git-diff", "HEAD"], cwd=str(repo)
    )
    assert result_ok.returncode == 0
    assert "OWNS OK: 2 paths within 2 declared" in result_ok.stdout

    # Сузь owns до ОДНОГО tracked-файла -- untracked теперь вне owns ->
    # OUT-OF-OWNS АБСОЛЮТНЫМ путём, exit 1.
    result_violation = _run_cli(
        ["--owns", tracked_abs, "--git-diff", "HEAD"], cwd=str(repo)
    )
    assert result_violation.returncode == 1
    assert f"OUT-OF-OWNS: {untracked_abs}" in result_violation.stdout


# ---------------------------------------------------------------------
# F1 (release-gate v0.8.1, критик-фикс): не-ASCII путь внутри
# объявленной owns-директории не должен давать ЛОЖНЫЙ OUT-OF-OWNS.
# Дефолт git'а (core.quotepath=true, локального оверрайда нигде в этих
# тестах нет) octal-эскейпит не-ASCII байты пути в выводе `ls-files
# --others` -- воспроизводимо на ЛЮБОЙ консольной локали/платформе,
# это дефолт конфига git, а не эффект кодовой страницы консоли, так
# что skip-маркер здесь не нужен.
# ---------------------------------------------------------------------


def test_cli_git_diff_non_ascii_untracked_path_no_false_out_of_owns(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_temp_git_repo(repo)

    tracked = repo / "tracked.py"
    tracked.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(repo), capture_output=True, check=True
    )

    owns_dir = repo / "owns_dir"
    owns_dir.mkdir()
    # untracked-файл с не-ASCII именем -- ровно тот код-путь
    # `ls-files --others`, который правит этот фикс.
    nonascii = owns_dir / "кафе.py"
    nonascii.write_text("x\n", encoding="utf-8")

    result = _run_cli(
        ["--owns", str(owns_dir.resolve()), "--git-diff", "HEAD"], cwd=str(repo)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OUT-OF-OWNS" not in result.stdout
    assert "OWNS OK: 1 paths within 1 declared" in result.stdout


def test_cli_git_diff_ascii_untracked_path_still_matches_owns_regression(tmp_path):
    # ASCII-регресс-пин рядом с не-ASCII тестом выше -- тот же
    # сценарий, чисто ASCII имя файла, должен резолвиться так же чисто
    # после фикса encoding/quotepath.
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_temp_git_repo(repo)

    tracked = repo / "tracked.py"
    tracked.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=str(repo), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(repo), capture_output=True, check=True
    )

    owns_dir = repo / "owns_dir"
    owns_dir.mkdir()
    ascii_file = owns_dir / "plain.py"
    ascii_file.write_text("x\n", encoding="utf-8")

    result = _run_cli(
        ["--owns", str(owns_dir.resolve()), "--git-diff", "HEAD"], cwd=str(repo)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OUT-OF-OWNS" not in result.stdout
    assert "OWNS OK: 1 paths within 1 declared" in result.stdout
