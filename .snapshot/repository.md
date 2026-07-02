# Repository Export

Automatically generated.
Do not edit manually.

================================================================================
FILE: ANTI_GOALS.md
================================================================================

# Anti Goals

This project is NOT:

- an AGI project;
- another agent framework;
- a replacement for existing LLMs;
- an attempt to maximize the number of agents;
- architecture for architecture's sake.


================================================================================
FILE: apply.py
================================================================================

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

        else:
            raise ValueError(
                f"Unsupported operation: {op_type}"
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


================================================================================
FILE: BOOT.md
================================================================================

# Boot Sequence

The repository is the only source of truth.

When starting a new conversation:

1. Read README.md.
2. Read PROJECT_CHARTER.md.
3. Read PROJECT_PHILOSOPHY.md.
4. Read ANTI_GOALS.md.
5. Read DECISIONS.md.
6. Read MEMORY_ARCHITECTURE.md.
7. Read ROADMAP.md.
8. Read CURRENT_CONTEXT.md if it exists.

After loading these documents:

- summarize the current state;
- identify the current milestone;
- identify the next objective;
- continue the work.

If repository contents conflict with chat history, the repository always wins.


================================================================================
FILE: CONTRIBUTING.md
================================================================================

# Contributing

## Workflow

Discussion → Decision → Implementation.

Large architectural changes should be documented before implementation.

Keep commits small and logically complete.


================================================================================
FILE: CURRENT_CONTEXT.md
================================================================================

# Current Context

## Current Milestone

Milestone 1 — Repository-Aware Lead

## Current Status

Repository foundation completed.
Kernel supports operation-based patches.
Documentation structure established.
Memory architecture defined.

## Current Objective

Investigate repository-aware context loading.

## Next Tasks

- Validate GitHub Connector capabilities.
- Design Repository Memory Manager.
- Define Context Builder.

This file is intended to be updated frequently.


================================================================================
FILE: DECISIONS.md
================================================================================

# Decisions Log

## D-0001
Git is the single source of truth.

## D-0002
English is the canonical project language.
Russian is a synchronized translation.

## D-0003
Engineering over Perfection.

## D-0004
The project consists of a White Paper, Architecture Specification and Reference Implementation.

## D-0005
Kernel must remain independent of any specific LLM.

## D-0006
Project memory is layered.

## D-0007
Every document must be reachable from repository navigation.

## D-0008
Every Patch must leave the repository in a consistent, navigable state.

## D-0009
Repository content overrides chat history.

## D-0010
BOOT.md defines the canonical repository loading sequence.

## D-0011
SYSTEM_PROMPT.md defines permanent behavioural rules.

## D-0012
Every commit must improve the repository as a complete knowledge system.

## D-0013
Recurring engineering practices must be documented as repository protocols.

## D-0014
No important project knowledge may remain only inside chat history.

## D-0015
The repository stores both project knowledge and engineering processes.

## D-0016
A commit should represent exactly one conceptual change.

## D-0017
Validate Before Elaborating.
Implement new architectural layers only after validating the previous ones.

## D-0018
Infrastructure Before Features.
Improve development infrastructure before relying on new capabilities.


================================================================================
FILE: docs/adr/README.md
================================================================================

# Architecture Decision Records

This directory contains long-term architectural decisions.


================================================================================
FILE: docs/book/en/README.md
================================================================================

# English Edition

This directory contains the canonical version of the book.


================================================================================
FILE: docs/book/ru/README.md
================================================================================

# Русское издание

Эта директория содержит синхронизированный перевод английской версии.


================================================================================
FILE: docs/README.md
================================================================================

# Documentation

## Engineering Process

See ../PROCESS/README.md


================================================================================
FILE: docs/SESSION_START.md
================================================================================

# Starting a New Session

The recommended way to continue work on this project is:

Resume Operating-System-for-LLMs.

Repository:
https://github.com/Xartaxana/Operating-System-for-LLMs

Follow BOOT.md.

The assistant should restore project state from the repository before proposing any changes.


================================================================================
FILE: export_repo.py
================================================================================

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


================================================================================
FILE: hello.md
================================================================================

# Hello

This file was created automatically.


================================================================================
FILE: MEMORY_ARCHITECTURE.md
================================================================================

# Memory Architecture

## Purpose

The project treats memory as a first-class subsystem.

The objective is to make project continuity independent from any particular LLM or chat history.

---

## Principle 1 — Git is the source of truth

Git is the only long-term memory.

Chat conversations are temporary workspaces.

No important project knowledge should exist only inside a conversation.

---

## Principle 2 — Layered Memory

### Layer 1 — Constitution

Always loaded.

Includes:
- PROJECT_CHARTER.md
- PROJECT_PHILOSOPHY.md
- ANTI_GOALS.md

### Layer 2 — Decisions

Architectural knowledge.

Includes:
- DECISIONS.md
- ADR/*

### Layer 3 — Operational State

Current status of the project.

Includes:
- ROADMAP.md
- CURRENT_CONTEXT.md (future)

### Layer 4 — Repository History

Complete Git history.

Never fully injected into an LLM context.

Retrieved on demand.

---

## Principle 3 — Context Manager

LLMs should not remember project rules.

A Context Manager prepares the appropriate context from Git before every reasoning session.

---

## Principle 4 — Constitution is Mandatory

The Constitution layer is always included in the reasoning context.

This prevents architectural drift.

---

## Principle 5 — Full Repository Access

The operating system must always have access to the complete repository.

Only the loaded context is selective.

Storage is complete.


================================================================================
FILE: patch.json
================================================================================

{
  "commit": "feat(kernel): add repository snapshot generator",
  "operations": [
    {
      "type": "create",
      "path": "snapshot.py",
      "content": "import hashlib\nimport json\nfrom pathlib import Path\n\nROOT = Path(__file__).parent\nSNAPSHOT = ROOT / '.snapshot'\n\nIGNORE = {\n    '.git',\n    '.snapshot',\n    '__pycache__',\n    '.venv',\n    'venv'\n}\n\n\ndef sha256(path):\n    h = hashlib.sha256()\n    with open(path, 'rb') as f:\n        while True:\n            chunk = f.read(65536)\n            if not chunk:\n                break\n            h.update(chunk)\n    return h.hexdigest()\n\n\ndef build_tree(directory, prefix=''):\n    lines = []\n\n    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))\n\n    for entry in entries:\n\n        if entry.name in IGNORE:\n            continue\n\n        rel = entry.relative_to(ROOT)\n\n        if entry.is_dir():\n            lines.append(prefix + rel.as_posix() + '/')\n            lines.extend(build_tree(entry, prefix + '    '))\n        else:\n            lines.append(prefix + rel.as_posix())\n\n    return lines\n\n\ndef build_index():\n\n    result = []\n\n    for path in sorted(ROOT.rglob('*')):\n\n        rel = path.relative_to(ROOT)\n\n        if any(part in IGNORE for part in rel.parts):\n            continue\n\n        if path.is_file():\n            result.append({\n                'path': rel.as_posix(),\n                'sha256': sha256(path),\n                'size': path.stat().st_size\n            })\n\n    return result\n\n\ndef main():\n\n    SNAPSHOT.mkdir(exist_ok=True)\n\n    tree = build_tree(ROOT)\n\n    (SNAPSHOT / 'tree.md').write_text(\n        '\\n'.join(tree),\n        encoding='utf-8'\n    )\n\n    index = build_index()\n\n    with open(SNAPSHOT / 'files.json', 'w', encoding='utf-8') as f:\n        json.dump(index, f, indent=2)\n\n    print('Snapshot created.')\n    print(SNAPSHOT / 'tree.md')\n    print(SNAPSHOT / 'files.json')\n\n\nif __name__ == '__main__':\n    main()\n"
    },
    {
      "type": "update",
      "path": "README.md",
      "content": "# Operating System for LLMs\n\nAn open research project exploring hierarchical orchestration of Large Language Models.\n\nThe repository is the project's single source of truth.\n\n## Repository Snapshot\n\nRun:\n\n```\npython snapshot.py\n```\n\nThis creates:\n\n```\n.snapshot/tree.md\n.snapshot/files.json\n```\n\nThese files provide a reproducible snapshot of the repository structure and are intended to be shared with an LLM before generating a Patch.\n\n## Engineering Process\n\nSee PROCESS/README.md.\n"
    }
  ]
}


================================================================================
FILE: PROCESS/DOCUMENTATION_PROTOCOL.md
================================================================================

# Documentation Protocol

Every document must:

- Have a clear purpose.
- Be reachable from repository navigation.
- Avoid duplicated information.
- Reference related documents where appropriate.

The repository should function as a coherent knowledge graph.


================================================================================
FILE: PROCESS/PATCH_PROTOCOL.md
================================================================================

# Patch Protocol

A Patch is the only approved mechanism for changing the repository.

Every Patch should:

1. Solve one conceptual problem.
2. Preserve repository consistency.
3. Update affected documentation.
4. Leave the repository in a self-contained state.
5. Avoid hidden knowledge.


================================================================================
FILE: PROCESS/PRE_COMMIT_PROTOCOL.md
================================================================================

# Pre-Commit Protocol

Execute before preparing every Patch.

## Repository Integrity

- Repository remains self-contained.
- No orphan documents.
- Every new document is linked.
- README navigation updated.
- Documentation index updated.
- Cross-references verified.

## Knowledge Integrity

- No duplicated information.
- Existing documents updated when appropriate.
- New project rules recorded.
- Roadmap updated if milestone changes.
- Architecture updated if system structure changes.

## Engineering Integrity

- Engineering over Perfection.
- Measure Before Optimizing.
- Validate Before Elaborating.

## Patch Quality

- One conceptual change.
- Small verifiable improvement.
- Repository understandable without chat history.


================================================================================
FILE: PROCESS/README.md
================================================================================

# Engineering Process

This directory contains the engineering protocols that define how the project evolves.

The project must not depend on any individual LLM remembering the workflow.

The repository stores both project knowledge and engineering processes.

## Protocols

- PRE_COMMIT_PROTOCOL.md
- PATCH_PROTOCOL.md
- SESSION_PROTOCOL.md
- DOCUMENTATION_PROTOCOL.md


================================================================================
FILE: PROCESS/SESSION_PROTOCOL.md
================================================================================

# Session Protocol

## Session Start

1. Connect the repository.
2. Follow BOOT.md.
3. Restore CURRENT_CONTEXT.md.
4. Continue the work.

## Session End

Before ending a session:

- Record new decisions.
- Update roadmap if necessary.
- Update architecture if necessary.
- Update current context.
- Produce a Patch.

No important knowledge should remain only inside chat history.


================================================================================
FILE: PROJECT_CHARTER.md
================================================================================

# Project Charter

## Mission

Design and build an open architecture for efficient orchestration of multiple LLMs.

## Time Horizon

The project is expected to evolve over several months.
The objective is a working architecture before the ecosystem changes significantly.

## Primary Deliverables

1. White Paper
2. Architecture Specification
3. Reference Implementation

## Core Principles

- Engineering over Perfection.
- Git is the single source of truth.
- Decisions must be documented.
- Every architectural claim should eventually be validated experimentally.
- Build the smallest working system first.


================================================================================
FILE: PROJECT_PHILOSOPHY.md
================================================================================

# Project Philosophy

## Engineering over Perfection

Prefer simple, measurable and working solutions over ideal but impractical designs.

## Measure Before Optimizing

Optimization without measurements is speculation.

## Escalation is a Resource

Powerful models are expensive resources and should be used intentionally.

## Simplicity Wins

Every new component must justify its existence.

## Git is Memory

The repository is the project's memory.
Chat conversations are not.


================================================================================
FILE: README.md
================================================================================

# Operating System for LLMs

An open research project exploring hierarchical orchestration of Large Language Models.

The repository is the project's single source of truth.

## Repository Snapshot

Run:

```
python snapshot.py
```

This creates:

```
.snapshot/tree.md
.snapshot/files.json
```

These files provide a reproducible snapshot of the repository structure and are intended to be shared with an LLM before generating a Patch.

## Engineering Process

See PROCESS/README.md.


================================================================================
FILE: ROADMAP.md
================================================================================

# Roadmap

## Phase 0

- [x] Automatic commits
- [x] Patch protocol
- [x] Project foundation
- [x] Memory architecture
- [x] Boot sequence

## Phase 1

Repository-aware assistant.

Goals:

- Read repository.
- Restore project state.
- Build context automatically.
- Continue work without chat history.


================================================================================
FILE: snapshot.py
================================================================================

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
SNAPSHOT = ROOT / '.snapshot'

IGNORE = {
    '.git',
    '.snapshot',
    '__pycache__',
    '.venv',
    'venv'
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def build_tree(directory, prefix=''):
    lines = []

    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))

    for entry in entries:

        if entry.name in IGNORE:
            continue

        rel = entry.relative_to(ROOT)

        if entry.is_dir():
            lines.append(prefix + rel.as_posix() + '/')
            lines.extend(build_tree(entry, prefix + '    '))
        else:
            lines.append(prefix + rel.as_posix())

    return lines


def build_index():

    result = []

    for path in sorted(ROOT.rglob('*')):

        rel = path.relative_to(ROOT)

        if any(part in IGNORE for part in rel.parts):
            continue

        if path.is_file():
            result.append({
                'path': rel.as_posix(),
                'sha256': sha256(path),
                'size': path.stat().st_size
            })

    return result


def main():

    SNAPSHOT.mkdir(exist_ok=True)

    tree = build_tree(ROOT)

    (SNAPSHOT / 'tree.md').write_text(
        '\n'.join(tree),
        encoding='utf-8'
    )

    index = build_index()

    with open(SNAPSHOT / 'files.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

    print('Snapshot created.')
    print(SNAPSHOT / 'tree.md')
    print(SNAPSHOT / 'files.json')


if __name__ == '__main__':
    main()


================================================================================
FILE: SYSTEM_PROMPT.md
================================================================================

# System Prompt

This document defines the permanent behaviour expected from any LLM working on this repository.

Core principles:

- Git is the only source of truth.
- Chat is only a temporary workspace.
- Engineering over Perfection.
- Measure Before Optimizing.
- Small verifiable improvements.
- Never invent missing project state.
- Always retrieve project knowledge from the repository.
- Repository content overrides chat history.
- Every architectural decision should eventually be documented.


