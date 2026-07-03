# Operating System for LLMs

An open research project exploring hierarchical orchestration of Large Language Models.

The repository is the project's single source of truth.

## Architecture

See ARCHITECTURE.md for the authoritative architecture specification
and DELEGATION_TABLE.md for the living delegation cost/value table.

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
