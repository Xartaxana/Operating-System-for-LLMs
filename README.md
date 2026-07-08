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

## Unified Plan

See docs/UNIFIED_PLAN_2026-07-07.md — the adopted plan of record
merging the repository roadmap with the external Claude Code routing
plan (D-0034..D-0036). ROADMAP.md holds the phase/gate structure.

## Review Reports and External Inputs

See docs/EXTERNAL_REVIEW_CONTEXT_MANAGEMENT_2026-07-04.md for the
2026-07-04 external review of project positioning, context management
and Phase 2 development options, and
docs/EXTERNAL_PLAN_CLAUDE_CODE_ROUTING_2026-07-07.md for the external
routing plan merged on 2026-07-07.

## Findings

See docs/FINDINGS.md — the registry of empirical findings from
dogfooding the architecture on both contours (distinct from
docs/RELATED_WORK.md, which holds external priors); entries summarize
and point to the canonical evidence, which stays in place.
docs/SIBLING_MAP.md is the symmetry-axis map that makes the D-0043
"fix the class" sweep a targeted lookup instead of a repo rescan. Routing policy for
this repository lives in CLAUDE.md (auto-loaded) with tiered subagents
in .claude/agents/ and the delegation journal in logs/routing-log.jsonl.

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
