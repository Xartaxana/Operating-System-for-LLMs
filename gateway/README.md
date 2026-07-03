# Gateway

Phase 1 steps 1–4 (see ARCHITECTURE.md: "Gateway", "Guard", "Ledger", "Analyst").

A LiteLLM proxy that all real model traffic passes through.
Every request — successful or failed — is recorded in a SQLite log
that the Ledger (Phase 1 step 3) will consume. Raw prompt text is
stored because the context-repetition ratio needs it.

The Guard enforces daily per-model budgets deterministically inside
the request path: a `warn` event at 80% of budget (once per model per
day), HTTP 429 refusal at 100%. Budgets live in `budgets.yaml` and are
re-read on every request — edits apply without a proxy restart.

Why not LiteLLM's native budgets (D-0030 evaluation): they require
Postgres (and Redis for cross-worker counters), both explicitly
deferred by ARCHITECTURE.md, and lack per-model 80%-warning semantics.
The Guard is ~100 lines over the SQLite log the gateway already writes.

## Files

- `config.yaml` — proxy configuration (models, callback registration).
- `sqlite_logger.py` — LiteLLM custom callback writing to SQLite.
- `guard.py` — budget enforcement pre-call hook (no LLM).
- `budgets.yaml` — daily budgets per gateway alias; `GATEWAY_BUDGETS_PATH` overrides.
- `metrics.py` — the Ledger: daily digest over the request log (no LLM).
- `analyst.py` — the Analyst: local small model narrating the digest.
- `shadow_eval.py` — Shadow Evaluation: replay + compare, updates DELEGATION_TABLE.md.
- `test_sqlite_logger.py`, `test_guard.py`, `test_metrics.py`, `test_analyst.py`, `test_shadow_eval.py` — tests, no API keys required.
- `requests.db` — the request log (created on first request, not committed).
  Also holds the `budget_events` table (warn/block history for the Ledger).

## Run

```
pip install -r requirements.txt
cd gateway
litellm --config config.yaml
```

The proxy serves an OpenAI-compatible API on http://localhost:4000.

Models (gateway aliases → ARCHITECTURE.md hierarchy):

- `lead` — frontier model via Anthropic API; needs `ANTHROPIC_API_KEY` (paid).
- `intern` — local Qwen3-4B via Ollama; free, no keys. Synthetic
  per-token prices (Haiku-class) are configured so Guard/Ledger money
  paths work without real spend.
- `analyst` — same local model under its own alias, so the Ledger
  accounts supervision cost separately (Rule #1).
- `mock` — canned response, for smoke tests.

Free-telemetry mode: with only Ollama installed (`ollama pull qwen3:4b`),
traffic to `intern`/`analyst` produces full real telemetry at $0.

Set `GATEWAY_DB_PATH` to override the log location (default: `gateway/requests.db`).

On Windows also set `PYTHONUTF8=1`: with a non-UTF-8 console codepage
(e.g. cp1251) the proxy crashes on startup printing its banner.

Run the proxy FROM the gateway/ directory: LiteLLM imports the callback
modules (`sqlite_logger`, `guard`) relative to the working directory.

Ollama on old NVIDIA drivers: CUDA kernels fail with "PTX compiled
with an unsupported toolchain" and the request errors out. Fix: update
the driver — for Pascal cards (GTX 10xx) Game Ready drivers ended in
2025, but the 580-branch security drivers (e.g. 582.28) are full
drivers and resolve this (verified on GTX 1060: driver 560.94 failed,
582.28 runs Qwen3-4B 100% on GPU, ~3x faster than CPU). Temporary
workaround: CPU mode via `CUDA_VISIBLE_DEVICES=-1 ollama serve`.

## Smoke test without API keys

The `mock` model in `config.yaml` returns a canned response without
calling any provider (a `mock_response` field in the request body is
NOT forwarded by the proxy — the mock must live in the model config):

```
curl http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer anything" -d "{\"model\": \"mock\", \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}]}"
```

The request is logged like any other, so a `success` row for model
`mock` must appear in `requests.db`.

## Ledger digest

```
python metrics.py [--db PATH] [--days N] [--json]
```

Reports per model per day: requests, failures, tokens, cost, latency,
answer length; the context-repetition ratio (share of prompt characters
already sent in the previous request of the same model — computed as a
common-prefix overlap, which matches append-only conversation history);
task categories by transparent keyword heuristics (estimates for the
delegation table, refined later by the Analyst); and budget events.
`--json` emits the same digest machine-readable for the Analyst (step 4).

## Analyst

```
python analyst.py "why was today expensive?" [--days N]
python analyst.py --digest-only        # inspect what the model sees
```

The Analyst feeds the Ledger digest (never raw conversations) to the
local model through the gateway and answers operator questions.
Requires the proxy and Ollama running.

## Shadow Evaluation

```
python shadow_eval.py --source-model lead --target-model intern [--days N] [--sample N] [--update-table] [--json]
```

Samples successful requests logged for `--source-model`, replays each
prompt on `--target-model` through the gateway, and compares answers
with a transparent heuristic (character-level similarity via
`difflib`; an LLM judge can replace this later without changing the
pipeline — same "estimate, mark it as such" spirit as `metrics.categorize`).
Results are grouped by the same keyword-heuristic task category
`metrics.py` uses. A category needs `--min-samples` (default 2)
before it can move off `estimated`; source and target must differ —
comparing a model to itself is not evidence of delegation.

`--update-table` writes `validated`/`rejected` verdicts into
`DELEGATION_TABLE.md` row Status cells and appends one line per run to
its "Shadow Evaluation Log" section (evidence for Update Rule 1).

Caveat (Update Rule 4): this replays each prompt once. It measures
one-shot answer quality and cost, not retry-loop cost — a category
marked `validated` here has not yet been checked against the "cheap
model needs 10 retries" failure mode rule 4 warns about.

Needs real `--source-model` traffic in the log first (e.g. `lead`,
once `ANTHROPIC_API_KEY` is set, or another paid/free-tier alias) —
comparing `intern` against itself does not validate anything.

## Tests

```
python -m pytest gateway/
```

Note on thresholds: the 80% warning uses float comparison; a spend
sitting exactly on the boundary may not trigger it (observed:
0.8 × 0.025 > 0.02 in IEEE 754). Harmless in practice — the next
request over the line warns.

## Log schema

Table `requests`: `ts`, `model` (gateway alias the client asked for),
`provider_model` (resolved underlying model), `status` (success/failure), `latency_ms`,
`prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`,
`prompt` (messages JSON), `response` (completion text), `error`.
