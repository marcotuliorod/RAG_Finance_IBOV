# ADR-003: Retrieval Strategy

## Status

Accepted.

## Context

Given ADR-002's decision to use SQL + full-text search rather than vector
retrieval, this ADR covers the specific retrieval design choices within
that approach: how numeric queries are structured, how textual search is
ranked, and what was deliberately left out (reranking, hybrid search,
retrieval-quality metrics).

## Decision

- **Numeric retrieval** exposes 7 specific, purpose-built query shapes as
  tools (latest bar, variation between dates, variation over N trading
  days, extreme in a range, all-time high, period summary, period
  comparison) rather than one generic "query the database" tool. Each has
  its own JSON Schema and dedicated SQL function
  (`src/rag_b3/query/ibov_numeric.py`).
- **Textual retrieval** exposes 2 tools (latest-by-feed for recency
  questions, keyword search for everything else), ranked by
  `ts_rank(...) desc, published_at desc`, capped at `limit ≤ 50`
  (`_clamp_limit`, added Session 4 after a real unbounded-limit finding —
  see `docs/security/AI_SECURITY.md`).

## Alternatives considered

| Option | Why not chosen |
|---|---|
| One generic "run SQL" tool | Would reintroduce SQL-injection risk and give the model far more capability than the read-only, narrowly-scoped tool set this system relies on for its security posture (`docs/ai/tool-calling.md`, `docs/security/AI_SECURITY.md` §"Excessive Agency"). |
| Reranking on top of `tsvector` results | No measured benefit at 60 items — both retrieval-dependent golden dataset cases already score faithfulness 1.00 without it (`docs/evaluation/baseline.md`). Would add complexity and latency for no evidenced quality gain. |
| Hybrid (lexical + vector) search | Requires a vector leg to hybridize with, which ADR-002 already ruled out for this corpus size. |
| Precision@K/Recall@K/MRR as hard evaluation metrics | Attempted (Session 2) and explicitly not built — no reliable ground-truth relevant-set exists against a live-updating CVM feed without freezing a snapshot to hand-label against (`docs/evaluation/methodology.md` limitation note). Faithfulness/relevancy substitute as an end-to-end correctness signal instead. |

## Trade-offs

Purpose-built tools (7 numeric shapes instead of 1 generic query tool) mean
more code to maintain per new query pattern, but each tool's input schema
is precise enough that the model rarely needs multiple rounds to get the
right data — the real measured data shows most cases resolve in 1-2 tool
calls, with only genuinely multi-hop questions (e.g. golden case 011)
needing 3 (`docs/cost-performance.md`).

## Consequences

- Adding a new query shape (e.g., "compare 3 periods" instead of 2) means
  adding a new tool + SQL function, not just a prompt change — a real
  maintenance cost, accepted in exchange for keeping every tool's behavior
  exact and testable in isolation (`tests/integration/test_ibov_numeric.py`).
- Retrieval-quality metrics remain a documented gap (not a silent one) —
  revisit if the CVM feed's role in the system grows beyond "answer
  recency/keyword questions over ~60 items."
