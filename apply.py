import json
import subprocess
from pathlib import Path


PATCH_FILE = "patch.json"


def git(*args):
    """Run a git command and stop on error."""
    print(">", "git", *args)

    result = subprocess.run(
        ["git", *args],
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError("Git command failed")


def main():

    repo = Path(__file__).parent

    patch_path = repo / PATCH_FILE

    if not patch_path.exists():
        raise FileNotFoundError(PATCH_FILE)

    with open(patch_path, "r", encoding="utf-8") as f:
        patch = json.load(f)

    files = patch.get("files", [])

    for file in files:

        path = repo / file["path"]

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            file["content"],
            encoding="utf-8"
        )

        print("Created:", path)

    git("add", ".")

    git("commit", "-m", patch["commit"])

    git("push")

    print()
    print("SUCCESS")
    print("Patch applied.")


if __name__ == "__main__":
    main()