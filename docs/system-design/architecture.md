# System Design — Architecture

Full component-level detail lives in `docs/architecture/` (overview,
data-flow, rag-pipeline, ai-architecture, deployment) — this document is
the system-design-level summary an interviewer would want first, with
pointers to the detail.

## The one-sentence architecture

A FastAPI app takes a natural-language question, hands it to Claude with 9
read-only SQL/full-text-search tools, and returns Claude's answer grounded
entirely in what those tools returned — with a completely separate,
independently-scheduled set of jobs keeping the underlying Postgres data
fresh.

## Why this shape

- **Synchronous chat, asynchronous ingestion** — these have fundamentally
  different failure/latency/scheduling needs (a chat request needs a
  response in seconds; ingestion can retry over minutes) and are cleanly
  separated rather than coupled through, say, an in-request "check if data
  is stale and refresh it" path.
- **Read path is tool-calling, not embedding retrieval** — see ADR-002.
  This is the architectural choice most likely to be probed in an
  interview, and the honest answer is "matched to this corpus's shape, not
  a general RAG recommendation" (see `docs/adr/ADR-002-rag-architecture.md`).
- **One database, no service mesh, no message queue** — appropriate for a
  single-user system with ~2,700 total rows across its two content tables.
  A queue or event bus here would be solving a scale problem this system
  doesn't have.

## Layering

```
User → FastAPI (web/) → Generation loop (generation/) → Tools (generation/tools.py)
                                                            ├─ Numeric query (query/)
                                                            └─ Textual retrieval (retrieval/)
                                                                  └─ Postgres
```

Each layer has a single, narrow responsibility: `web/` only handles
HTTP/validation/error-shaping, `generation/` only orchestrates the
tool-use loop, `query/`+`retrieval/` only know how to answer their specific
kind of question, and nothing above the tool layer ever touches SQL
directly.

## What would need to change to scale this to more users

Not built (single-user scope), but worth stating precisely what the
bottlenecks would actually be, since "would this scale" is the natural
follow-up question:

1. **Connection handling** — `common/db.py` opens one `psycopg.connect()`
   per request with no pooling. Fine at low concurrency; would need a
   connection pool (`psycopg_pool`) before meaningfully higher concurrent
   load.
2. **No caching** — every request re-queries Postgres and re-calls the
   LLM, even for repeated/similar questions. A cache keyed on
   (normalized-question → answer) with a short TTL would cut both latency
   and LLM cost for a multi-user version, at the cost of potential
   staleness the system would need to bound explicitly.
3. **Auth/multi-tenancy** — currently no user concept exists at all
   (ADR-007); this is the largest actual redesign, not a scaling tweak.

See `scalability.md` for the fuller treatment.
