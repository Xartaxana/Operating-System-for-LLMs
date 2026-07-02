import json
import subprocess
import sys
from pathlib import Path

PATCH_FILE = "patch.json"


def git(*args):
    """Run a git command and stop on error."""
    print(">", "git", *args)

    result = subprocess.run(["git", *args], text=True)

    if result.returncode != 0:
        raise RuntimeError("Git command failed")


def create_file(repo, op):
    path = repo / op["path"]

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        op.get("content", ""),
        encoding="utf-8"
    )

    print("Created:", path)


def delete_file(repo, op):
    path = repo / op["path"]

    if path.exists():
        path.unlink()
        print("Deleted:", path)


def apply_old_format(repo, patch):
    files = patch.get("files", [])

    for file in files:
        create_file(repo, file)


def apply_new_format(repo, patch):
    operations = patch.get("operations", [])

    for op in operations:

        op_type = op["type"]

        if op_type == "create":
            create_file(repo, op)

        elif op_type == "delete":
            delete_file(repo, op)

        else:
            raise ValueError(f"Unsupported operation: {op_type}")


def main():

    repo = Path(__file__).parent

    patch_path = repo / PATCH_FILE

    if not patch_path.exists():
        raise FileNotFoundError(PATCH_FILE)

    with open(patch_path, "r", encoding="utf-8") as f:
        patch = json.load(f)

    if "operations" in patch:
        print("Patch format: operations")
        apply_new_format(repo, patch)

    elif "files" in patch:
        print("Patch format: files")
        apply_old_format(repo, patch)

    else:
        raise ValueError(
            "Patch must contain either 'operations' or 'files'."
        )

    git("add", ".")

    git("commit", "-m", patch["commit"])

    git("push")

    print()
    print("SUCCESS")
    print("Patch applied.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print()
        print("ERROR:", e)
        sys.exit(1)