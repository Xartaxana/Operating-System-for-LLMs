import json
import shutil
import subprocess
import sys
from pathlib import Path

PATCH_FILE = "patch.json"


def git(*args):
    print(">", "git", *args)

    result = subprocess.run(
        ["git", *args],
        text=True
    )

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


def update_file(repo, op):
    path = repo / op["path"]

    path.write_text(
        op.get("content", ""),
        encoding="utf-8"
    )

    print("Updated:", path)


def delete_file(repo, op):
    path = repo / op["path"]

    path.unlink()

    print("Deleted:", path)


def append_file(repo, op):
    path = repo / op["path"]

    if not path.exists():
        raise FileNotFoundError(path)

    with open(path, "a", encoding="utf-8") as f:
        f.write(op.get("content", ""))

    print("Appended:", path)
    

def replace_in_file(repo, op):
    path = repo / op["path"]

    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8")

    find = op["find"]
    replace = op["replace"]

    if find not in text:
        raise ValueError(
            f"Text not found in {path}: {find!r}"
        )

    text = text.replace(find, replace, 1)

    path.write_text(text, encoding="utf-8")

    print("Replaced:", path)


def insert_after(repo, op):
    path = repo / op["path"]

    if not path.exists():
        raise FileNotFoundError(path)

    text = path.read_text(encoding="utf-8")

    anchor = op["anchor"]
    content = op["content"]

    pos = text.find(anchor)

    if pos == -1:
        raise ValueError(
            f"Anchor not found in {path}: {anchor!r}"
        )

    pos += len(anchor)

    text = text[:pos] + content + text[pos:]

    path.write_text(text, encoding="utf-8")

    print("Inserted:", path)


def mkdir(repo, op):
    path = repo / op["path"]

    path.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Directory:", path)


def move(repo, op):
    source = repo / op["from"]
    destination = repo / op["to"]

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.move(
        str(source),
        str(destination)
    )

    print("Moved:", source, "->", destination)


def validate_patch(repo, patch):

    operations = patch.get("operations", [])

    seen = set()

    errors = []

    for op in operations:

        op_type = op["type"]

        if op_type == "mkdir":
            continue

        if op_type in ("create", "update", "delete"):

            path = repo / op["path"]

            if path in seen:
                errors.append(f"Duplicate operation for {path}")

            seen.add(path)

            if op_type == "create":

                if path.exists():
                    errors.append(f"Already exists: {path}")

            elif op_type == "update":

                if not path.exists():
                    errors.append(f"Missing file: {path}")

            elif op_type == "delete":

                if not path.exists():
                    errors.append(f"Missing file: {path}")

        elif op_type == "move":

            source = repo / op["from"]
            destination = repo / op["to"]

            if not source.exists():
                errors.append(f"Missing source: {source}")

            if destination.exists():
                errors.append(f"Destination exists: {destination}")

    if errors:

        print()

        print("VALIDATION FAILED")

        print()

        for e in errors:
            print("-", e)

        raise RuntimeError("Patch validation failed")


def apply_old_format(repo, patch):

    files = patch.get("files", [])

    for file in files:
        create_file(repo, file)


def apply_new_format(repo, patch):

    operations = patch.get("operations", [])

    validate_patch(repo, patch)

    print()

    print("Validation passed.")

    print()

    for op in operations:

        op_type = op["type"]

        if op_type == "mkdir":
            mkdir(repo, op)

        elif op_type == "create":
            create_file(repo, op)

        elif op_type == "update":
            update_file(repo, op)

        elif op_type == "delete":
            delete_file(repo, op)

        elif op_type == "move":
            move(repo, op)

        elif op_type == "append":
            append_file(repo, op)
            
        elif op_type == "replace":
            replace_in_file(repo, op) 

        elif op_type == "insert_after":
            insert_after(repo, op)    

        elif op_type in (
            "insert_before",
            "move",
            "validate"
                        ):
            raise NotImplementedError(
            f"Operation '{op_type}' is reserved for Patch Format v2."
    )


def load_patch(path):

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    repo = Path(__file__).parent

    if len(sys.argv) > 1:
        patch_path = repo / sys.argv[1]
    else:
        patch_path = repo / PATCH_FILE

    if not patch_path.exists():
        raise FileNotFoundError(patch_path)

    patch = load_patch(patch_path)

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