# Observability

## What's actually monitored today

This section states plainly what exists, to avoid the trap of describing
aspirational monitoring as if it were live. **There is no metrics
dashboard, no tracing, no alerting.** What exists is structured logging and
two append-only audit tables.

### API layer (`POST /api/ask`)

Added Session 2, extended Session 5. Every request logs one summary line on
success:

```
POST /api/ask ok: query_len=34 tool_calls=1 api_calls=2 input_tokens=5160 output_tokens=267 latency=5.66s model=claude-sonnet-5
```

Deliberately **never logs query or answer content** — only lengths/counts —
so a user pasting something sensitive into the chat doesn't end up in a log
file. `GenerationLoopExceededError` logs a warning; any other unhandled
exception is logged at error level with full traceback via the global
exception handler (Session 2).

### Generation layer (`generation/answer.py`)

**Added this session** — previously had zero logging (audit finding F-06).
Now logs:
- `DEBUG`: every tool call, by round number and tool name.
- `WARNING`: every tool call that returns `{"error": ...}` — not
  necessarily a bug (could be the correct "insufficient data" response),
  but worth visibility since it's a signal of either expected edge cases or
  unexpected LLM behavior (e.g. calling a tool with malformed input).
- `WARNING`: `GenerationLoopExceededError`, logged at the point of failure
  (not just at the web layer) so any caller — the web app, `scripts/run_eval.py`,
  a future batch script — gets the same signal.

### RAG / retrieval layer

No dedicated logging — retrieval calls are plain SQL functions
(`query/ibov_numeric.py`, `retrieval/cvm_textual.py`) called from
`generation/tools.py::execute_tool`, which is where the `DEBUG`/`WARNING`
logging above actually lives (one layer up). There is no separate
retrieval-latency measurement distinct from the overall generation latency
— see "What isn't measured" below.

### Ingestion layer

Unchanged from the Session 1 audit findings — already solid:
`ingestion_audit_log` (DB-backed, append-only, every external API call
logged with source/action/status/http_status/error_code/raw_response) and
`ingestion_job_run` (per-job-execution summary: start/finish/status/counts).
Plus stdlib logging in every ingestion module.

### Evaluation

`docs/evaluation/results/*.json` — every `scripts/run_eval.py` run persists
a full record (Session 2/3). `scripts/check_regression.py` reads the latest
one and reports PASS/FAIL. This is the closest thing this project has to a
"quality dashboard" today, and it's file-based, not a live service.

## What isn't measured (honest gaps, not hidden)

| Gap | Why it hasn't been built | Where it's tracked |
|---|---|---|
| Live metrics dashboard (request rate, error rate, latency percentiles over time) | Single-user, low-volume system — no Prometheus/OpenTelemetry integration exists, and building one for a system that gets a handful of requests a day would be effort disproportionate to the value, per the project's own "measure first, don't build for hypothetical scale" principle | `docs/audit/TECHNICAL_AUDIT.md` §8 (observability gaps) |
| Retrieval-specific latency (separate from total generation latency) | Retrieval calls are fast, indexed, single-table SQL against small tables (2,644 and 60 rows) — not currently a suspected bottleneck (see Cost & Performance below) | Same |
| LLM call retries/fallback tracking | No retry logic exists on LLM calls today (the Anthropic SDK's default `max_retries=2` applies transparently; nothing in this codebase adds its own retry/fallback layer) | Same |
| End-to-end distributed tracing | `constitution.md` already lists this as a considered-but-not-built future candidate (LangSmith/TruLens) | Same |
| Persistent, queryable request history (beyond log lines) | Would require a request-log table analogous to `ingestion_job_run` — reasonable future work if usage ever grows beyond "a few requests a day," not built now to avoid adding infrastructure for a volume that doesn't need it | This document |

## Sensitive-information discipline

Explicitly followed, not just claimed: query/answer text is never logged
(only lengths), exception messages are logged server-side only and never
returned to the client (Session 2 fix, tested in
`tests/unit/test_web_app.py`), and `.env` secrets are never logged (nothing
in the logging paths touches `settings.*_api_key`/`database_url` values).
