from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / ".snapshot" / "repository.md"

IGNORE_DIRS = {
    ".git",
    ".snapshot",
    "__pycache__",
    ".venv",
    "venv"
}

IGNORE_FILES = {
    "repository.md"
}

TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".json",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg"
}


def should_skip(path: Path) -> bool:
    if any(part in IGNORE_DIRS for part in path.parts):
        return True

    if path.name in IGNORE_FILES:
        return True

    if path.is_file() and path.suffix.lower() not in TEXT_EXTENSIONS:
        return True

    return False


def iter_files():
    files = []

    for path in ROOT.rglob("*"):

        if not path.is_file():
            continue

        if should_skip(path.relative_to(ROOT)):
            continue

        files.append(path)

    return sorted(files)


def main():

    OUT.parent.mkdir(exist_ok=True)

    with open(OUT, "w", encoding="utf-8") as out:

        out.write("# Repository Export\n\n")
        out.write("Automatically generated.\n")
        out.write("Do not edit manually.\n\n")

        for file in iter_files():

            rel = file.relative_to(ROOT).as_posix()

            out.write("=" * 80 + "\n")
            out.write(f"FILE: {rel}\n")
            out.write("=" * 80 + "\n\n")

            try:
                text = file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = file.read_text(
                    encoding="utf-8",
                    errors="replace"
                )

            out.write(text)

            if not text.endswith("\n"):
                out.write("\n")

            out.write("\n\n")

    print("Repository exported:")
    print(OUT)


if __name__ == "__main__":
    main()