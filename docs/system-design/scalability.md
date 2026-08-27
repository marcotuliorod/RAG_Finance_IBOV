# System Design — Scalability

## Current scale (real, measured — not projected)

- ~2,644 rows in `ibov_daily_history`, ~60 rows in `cvm_feed_item`
  (`docs/audit/TECHNICAL_AUDIT.md` §7).
- Single user, no concurrent-request testing has been done
  (`docs/cost-performance.md` explicitly notes this as untested, not
  assumed-fine).
- ~7.25s mean generation latency, dominated by LLM API round-trip time, not
  local compute (`docs/cost-performance.md`).

## What actually limits this system today

Nothing in the data layer — both tables are tiny, indexed, single-table
lookups. **The real ceiling is architectural, not a data-volume problem**:
one `psycopg.connect()` per request with no pooling, no caching, and no
concurrency testing. At current usage (a handful of requests a day from one
person) none of this matters. The honest answer to "how would this scale"
is a list of specific, known changes — not a vague "it would need work."

## Concrete scaling levers, in the order they'd actually become necessary

1. **Connection pooling** (`psycopg_pool.ConnectionPool` instead of a raw
   `psycopg.connect()` per request in `common/db.py`) — the first thing
   that would matter under any real concurrent load, since Postgres
   connection setup isn't free and the current code pays that cost on
   every single request.
2. **Read replicas / caching for the numeric table** — `ibov_daily_history`
   changes at most once a day (the daily ingestion job); every read of it
   is against data that's stale-safe to cache for hours. A simple
   in-process TTL cache on the 7 numeric query functions would cut
   Postgres load to near zero for the numeric path without any
   correctness risk, since the data genuinely doesn't change intra-day.
3. **Rate limiting** — currently absent (F-11) and would become load-bearing
   the moment this system has more than one trusted user, both for cost
   control (LLM calls aren't free) and for basic DoS resistance.
4. **Horizontal scaling of the FastAPI process itself** — not remotely
   necessary yet (uvicorn's default single-process setup handles this
   system's actual load trivially), but would be a straightforward
   `uvicorn --workers N` or a container replica count change once/if it
   ever mattered — no architectural blocker to it, since the app is
   already stateless per request (no in-memory session state anywhere in
   `web/app.py`).

## What does NOT need to scale

The ingestion side. Four jobs, running on independent schedules, each
touching a tiny amount of data (one API call to fetch a day's index value,
one poll of 6 RSS feeds) — this is not a throughput problem at any
plausible future scale for a single financial index and one regulator's
feed. `docs/architecture/data-flow.md` covers this path in detail.

## The honest trade-off

None of the above was built. Building connection pooling or caching for a
system that serves one person a handful of requests a day would be
premature optimization the project's own ground rules explicitly warn
against ("não otimize prematuramente... primeiro medir" —
`docs/cost-performance.md` applies the same principle here). This document
exists so that *if* scale ever becomes a real requirement, the answer isn't
a redesign from scratch — it's a known, ordered list of specific changes.
