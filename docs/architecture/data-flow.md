# Data Flow

Two independent flows share the same Postgres database: the **ingestion
flow** (asynchronous, scheduled) and the **query flow** (synchronous, one
request at a time). Neither blocks the other.

## Ingestion flow (asynchronous)

```mermaid
flowchart LR
    subgraph sources["Sources"]
        YF[Yahoo Finance chart API — unofficial]
        HG[HG Brasil API]
        BR[brapi.dev]
        CVM[CVM RSS x6 feeds]
    end

    subgraph jobs["Jobs — scripts/run_*.py, launchd-scheduled"]
        J1[run_ibov_backfill.py — occasional]
        J2[run_hg_brasil_ingestion.py — daily]
        J3[run_brapi_ingestion.py — daily]
        J4[run_cvm_poller.py — daily]
    end

    subgraph pipeline["Per-job pipeline"]
        R[tenacity retry — 3 attempts, exponential jitter]
        P[Parse/normalize — drop malformed, never fabricate]
        U[Idempotent upsert — ON CONFLICT]
    end

    subgraph store["Postgres"]
        T1[(ibov_daily_history)]
        T2[(cvm_feed_item)]
        AUDIT[(ingestion_audit_log — append-only)]
        RUN[(ingestion_job_run)]
    end

    YF --> J1 --> R --> P --> U --> T1
    HG --> J2 --> R
    BR --> J3 --> R
    CVM --> J4 --> R
    J2 --> U
    J3 --> U
    U --> T2
    J1 & J2 & J3 & J4 -.-> AUDIT
    J1 & J2 & J3 & J4 -.-> RUN
```

**Idempotency detail that matters:** backfill (`J1`) uses `ON CONFLICT DO
NOTHING` — it never overwrites a day already ingested by the daily job,
because the daily source is treated as more authoritative for the current
day. The daily jobs (`J2`) use `ON CONFLICT DO UPDATE` for the same reason
in reverse. This asymmetry is deliberate, not an oversight — see
`src/rag_b3/ingestion/yahoo_finance/repository.py:9-72`.

**Quota control:** `J2` (HG Brasil) reserves a request slot from a
Postgres-backed quota counter (`hg_brasil_quota_control`,
`reserve_hg_brasil_quota()`) *before* making the HTTP call — a pessimistic
reservation, since HG Brasil doesn't document quota-exceeded behavior in
advance.

## Query flow (synchronous, per-request)

```mermaid
sequenceDiagram
    participant U as User
    participant API as POST /api/ask
    participant Gen as generation/answer.py
    participant Claude as Anthropic API
    participant Tools as generation/tools.py
    participant DB as Postgres

    U->>API: {"query": "..."}
    API->>Gen: answer_question(conn, query)
    loop up to 5 tool-use rounds
        Gen->>Claude: messages.create(system, tools, messages)
        Claude-->>Gen: tool_use block(s) or final text
        alt tool_use
            Gen->>Tools: execute_tool(name, input)
            Tools->>DB: parameterized SQL
            DB-->>Tools: rows
            Tools-->>Gen: JSON result (or {"error": ...})
            Gen->>Claude: tool_result appended to messages
        else final text
            Gen-->>API: AnswerResult(text, tool_calls, usage, latency)
        end
    end
    API-->>U: {"answer": "...", "tool_calls": [...]}
```

If 5 rounds pass without a final text answer, `GenerationLoopExceededError`
is raised and surfaced as HTTP 502 — a deliberate fail-closed choice over
returning a partial/speculative answer.

## What's captured at each stage (as of this session)

| Stage | Captured | Not captured |
|---|---|---|
| Ingestion | Per-call audit log (source, action, status, http_status, error_code, raw_response), job-run summary | — |
| Query — generation | `input_tokens`, `output_tokens`, `api_calls`, `latency_seconds`, `model_id` on every `AnswerResult` (added this session, see `docs/evaluation/methodology.md`) | Per-request structured logs existed nowhere before this session; `POST /api/ask` now logs a summary line (query length, tool-call count, tokens, latency, model) without logging query/answer content |
| Query — retrieval | Nothing dedicated; folded into the tool_call log | Retrieval-specific latency (SQL execution time) is not separately timed from the overall generation latency |
