# Gateway

Phase 1 step 1 (see ARCHITECTURE.md, "Gateway").

A LiteLLM proxy that all real model traffic passes through.
Every request — successful or failed — is recorded in a SQLite log
that the Ledger (Phase 1 step 3) will consume. Raw prompt text is
stored because the context-repetition ratio needs it.

## Files

- `config.yaml` — proxy configuration (models, callback registration).
- `sqlite_logger.py` — LiteLLM custom callback writing to SQLite.
- `test_sqlite_logger.py` — logging-path tests, no API keys required.
- `requests.db` — the request log (created on first request, not committed).

## Run

```
pip install -r requirements.txt
cd gateway
litellm --config config.yaml
```

The proxy serves an OpenAI-compatible API on http://localhost:4000.
Point any OpenAI-compatible client at it with the model name `lead`.

Set `ANTHROPIC_API_KEY` in the environment before starting.
Set `GATEWAY_DB_PATH` to override the log location (default: `gateway/requests.db`).

On Windows also set `PYTHONUTF8=1`: with a non-UTF-8 console codepage
(e.g. cp1251) the proxy crashes on startup printing its banner.

## Smoke test without API keys

The `mock` model in `config.yaml` returns a canned response without
calling any provider (a `mock_response` field in the request body is
NOT forwarded by the proxy — the mock must live in the model config):

```
curl http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer anything" -d "{\"model\": \"mock\", \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}]}"
```

The request is logged like any other, so a `success` row for model
`mock` must appear in `requests.db`.

## Tests

```
python -m pytest gateway/test_sqlite_logger.py
```

## Log schema

Table `requests`: `ts`, `model` (gateway alias the client asked for),
`provider_model` (resolved underlying model), `status` (success/failure), `latency_ms`,
`prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`,
`prompt` (messages JSON), `response` (completion text), `error`.
