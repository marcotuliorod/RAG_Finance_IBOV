# System Design — Reliability

## Failure modes, and what happens for each (all verified in code, not assumed)

| Failure | What happens today | Evidence |
|---|---|---|
| LLM never converges to a final answer (loop/confusion) | `GenerationLoopExceededError` after 5 rounds → HTTP 502, not a speculative answer | `src/rag_b3/generation/answer.py`, `tests/unit/test_generation_answer.py` |
| A tool call fails with a domain error (insufficient data, bad input) | Converted to `{"error": ...}`, the model sees it and can respond honestly | `src/rag_b3/generation/tools.py`, `tests/security/test_injection_resistance.py` |
| A tool call fails with an unexpected DB error (`psycopg.DataError`) | **Fixed Session 4** — now caught and converted to a tool error with a defensive rollback, instead of crashing the request | Same, plus `docs/security/AI_SECURITY.md` §"Tool Abuse" |
| Any other unhandled exception (DB down, Anthropic API error) | Global exception handler logs full detail server-side, returns a generic 500 — never leaks internals | `src/rag_b3/web/app.py`, `tests/unit/test_web_app.py::test_ask_returns_generic_500_and_does_not_leak_exception_detail` |
| An ingestion source is temporarily down | `tenacity` retry (3 attempts, exponential jitter) on transient errors; malformed data is dropped, never fabricated | `docs/architecture/rag-pipeline.md` §Ingestion |
| One CVM feed (of 6) is malformed/down | Isolated per-feed — one failing feed doesn't stop the other 5 | `docs/audit/TECHNICAL_AUDIT.md` §6.1 |
| A model swap silently breaks grounding quality | Caught by the regression check (once wired into a scheduled CI run) — proven via unit test against the real historical Haiku regression numbers | `docs/evaluation/model-regression-case-study.md`, `tests/unit/test_eval_regression.py` |
| Re-running migrations against an already-migrated DB | **Fixed Session 6** — `schema_migrations` tracking table makes this a safe no-op | `scripts/apply_migrations.py` |

## What's NOT resilient, honestly stated

- **No retry on the LLM API call itself beyond the Anthropic SDK's own
  default** (`max_retries=2`, transparent) — no custom backoff/fallback
  logic exists in this codebase. Acceptable at current volume; would need
  attention for a higher-stakes deployment.
- **No database failover** — one Postgres instance, one named Docker
  volume. A disk failure loses data (though the numeric/CVM data is
  re-derivable from public sources via the ingestion jobs — see
  `docs/deployment/strategy.md` §Backup).
- **No circuit breaker on ingestion sources** — a persistently-failing
  source keeps retrying on its normal schedule rather than backing off
  further; acceptable given these are daily/occasional jobs, not
  high-frequency ones.
- **No concurrent-request testing** — the "what breaks under load" question
  is genuinely untested, not just undocumented (`scalability.md`).

## The single most important reliability property this system has

**It fails closed, not open, on the one failure mode that matters most:**
when the LLM can't ground an answer in real tool data, it says so instead
of guessing. This is true structurally (grounding is enforced by tool-use,
not by hoping the model behaves — `docs/architecture/ai-architecture.md`)
and confirmed empirically (all 4 adversarial golden dataset cases and both
data-boundary cases scored clean, correct refusals in the real 2026-08-27
evaluation runs — `docs/evaluation/baseline.md`). Every other reliability
concern in this document is secondary to this one holding.
