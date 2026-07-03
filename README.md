# Operating System for LLMs

An open research project exploring hierarchical orchestration of Large Language Models.

The repository is the project's single source of truth.

## White Paper

See WHITE_PAPER.md — living draft of the project's primary
deliverable (Supervised Delegation: an Operating System Approach to
LLM Cost).

## Architecture

See ARCHITECTURE.md for the authoritative architecture specification
and DELEGATION_TABLE.md for the living delegation cost/value table.

## Gateway

gateway/ contains the Phase 1 LiteLLM proxy with SQLite request logging.
See gateway/README.md.

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
