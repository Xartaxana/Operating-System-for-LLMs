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

- docs/FINDINGS.md — empirical findings from dogfooding (external
  priors live separately in docs/RELATED_WORK.md).
- docs/SIBLING_MAP.md — symmetry-axis map + failure-mode register; makes
  the D-0043 "fix the class" sweep a lookup, not a repo rescan.
- docs/RULE_COVERAGE.md — rule -> watching gate -> trigger mode.
- docs/OPERATIONAL_NOTES.md — on-demand operational reference,
  deliberately OFF the boot path: read before touching the
  proxy/gateway, the judge, or an argument about frontier share.
- CLAUDE.md — routing policy (auto-loaded); tiered subagents in
  .claude/agents/; delegation journal logs/routing-log.jsonl.
- delegation.config.yaml — the single carrier of this deployment's
  function→model binding (D-0099); the code gates resolve it from there.

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
