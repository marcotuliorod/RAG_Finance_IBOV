# ADR-006: Observability Approach

## Status

Accepted.

## Context

The system needed *some* visibility into request behavior — before Session
2/5, `generation/answer.py` and the web layer had zero logging, meaning a
failure or an odd model behavior left no trace at all
(`docs/audit/TECHNICAL_AUDIT.md` F-06). The question this ADR answers:
given a single-user, low-volume system, what level of observability
infrastructure is actually warranted?

## Decision

**Structured log lines, not a metrics/tracing stack.** Specifically:

- Per-request summary logging on `POST /api/ask` (query length, tool-call
  count, tokens, latency, model — never content).
- Per-tool-call `DEBUG` logging and per-tool-error `WARNING` logging in the
  generation loop.
- A global exception handler that logs full detail server-side, returns
  only a generic message to the client.
- Evaluation runs persisted as JSON artifacts (the closest thing to a
  metrics history this project has).

No Prometheus, no OpenTelemetry, no live dashboard for chat/generation
traffic (`src/rag_b3/dashboard/` remains ingestion-only).

## Alternatives considered

| Option | Why not chosen (yet) |
|---|---|
| Prometheus + Grafana | Real infrastructure to run and maintain for a system with a handful of requests a day — effort disproportionate to the value at current scale (`docs/observability.md`). |
| OpenTelemetry distributed tracing | Already listed as a considered-but-deferred future candidate in `constitution.md` before this project even started this transformation — reaffirmed, not newly rejected. |
| A request-history database table (like `ingestion_job_run`, but for chat) | Reasonable next step if usage ever grows — not built now because log lines already capture the same information at zero added infrastructure cost, and there's no current evidence anyone needs to *query* historical request data rather than just watch logs. |

## Trade-offs

Log lines are harder to aggregate/query than a metrics store once volume
grows, and there's no alerting. Acceptable today because there's exactly
one user and no on-call expectation; **explicitly not** acceptable if this
system is ever deployed for others to depend on — noted as a concrete
revisit trigger, not a permanent stance.

## Consequences

- Cost/latency analysis (`docs/cost-performance.md`) had to be done as a
  one-time manual pull from eval-run JSON artifacts rather than a live
  dashboard query — acceptable for a point-in-time report, would not scale
  to "check this every day" without building the request-history table
  option above.
- If Session 7/8's deployment decision (ADR-008) ever moves this system
  beyond single-user, this ADR should be revisited alongside the
  auth/rate-limiting decisions that same move requires.
