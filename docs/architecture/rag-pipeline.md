# RAG Pipeline — Deep Review

This is the Phase 2 pipeline review from the project roadmap. Per the
project's preservation rule, the goal here is to confirm what's correct and
change only what's justified — not to rewrite working code. **Conclusion
up front: no code changes were made to ingestion, retrieval, or context
assembly this session.** The only generation-layer change was additive
(engineering-metrics capture, see `docs/evaluation/methodology.md`) and does
not alter retrieval or grounding behavior.

## Ingestion

Reviewed: `src/rag_b3/ingestion/{yahoo_finance,hg_brasil,brapi,cvm_rss}/`.

| Concern | Finding | Verdict |
|---|---|---|
| Idempotency | `ON CONFLICT DO NOTHING` (backfill) vs. `ON CONFLICT DO UPDATE` (daily) — asymmetric by design, matching which source is authoritative for a given day | Correct, preserve |
| Retries | `tenacity`, 3 attempts, exponential jitter, only on transient errors (network/5xx) — never retries on malformed-data errors | Correct, preserve |
| Timeouts | Explicit per-client (15s Yahoo, `httpx.Timeout(connect=5, read=10, write=5, pool=5)` brapi) | Correct, preserve |
| Malformed data | Dropped, never fabricated (`client.py` docstring: "não inventamos dado onde a fonte não tem") | Correct, preserve |
| Duplicate handling | DB-level `ON CONFLICT`, plus CVM dedup key `(feed_key, guid)` | Correct, preserve |
| Timestamps / incremental updates | No true since-timestamp fetching — CVM re-polls whole feeds and dedups by guid; Yahoo backfill re-fetches whole range and dedups by date. This is a real limitation (re-fetches more than strictly necessary) but not a correctness bug — dedup means it's wasteful, not wrong. | Acceptable for current data volumes (~60 CVM items, single daily bar); revisit only if source API cost/rate limits make full re-fetch expensive |
| Logging | stdlib `logging` + DB-backed `ingestion_audit_log` (append-only via trigger) | Correct, preserve |
| The one real bug found in this codebase | Non-reproducible Yahoo backfill window (`range=10y` relative to call time vs. absolute `period1`/`period2`) — found and fixed in commit `412386b`, before this session | Already fixed; verified the fix is in place (`SERIES_START = date(2016, 1, 1)`, `src/rag_b3/ingestion/yahoo_finance/client.py`) |

**No changes made.** This layer is solid engineering already; nothing here
was flagged P0/P1 in the audit.

## Chunking

**Not applicable — confirmed absent by design, not missing by oversight.**
CVM feed items (title + summary, short RSS entries) are stored and searched
whole. There is no chunk-size/overlap parameter because there is nothing to
chunk: the corpus unit (one RSS item, one OHLC bar) is already the right
retrieval granularity. Introducing chunking here would add complexity
without benefit — reviewed and confirmed no change warranted.

## Embeddings

**Not applicable — confirmed absent by design.** No embedding model,
dimensionality, or cost applies. See `ai-architecture.md` for the full
rationale on why numeric SQL + full-text search was chosen over vector
similarity for this domain.

## Retrieval

Reviewed: `src/rag_b3/query/ibov_numeric.py`,
`src/rag_b3/retrieval/cvm_textual.py`.

- **Numeric retrieval** is exact point/range SQL (latest bar, variation
  between dates, extremes, period summary, comparisons) — there is no
  "top-k" or similarity concept because these are deterministic lookups,
  not approximate matches. `InsufficientDataError` carries the real series
  bounds so the model can cite them instead of guessing.
- **Textual retrieval** uses PostgreSQL `tsvector`/`plainto_tsquery('portuguese', ...)`
  ranked by `ts_rank(...) desc, published_at desc`, default `limit=5`,
  optional `feed_key` filter. No reranking, no hybrid search.
- **Reranking/hybrid search were evaluated and rejected as unnecessary**,
  confirmed again this session: the CVM corpus is ~60 items and growing
  slowly; `tsvector` ranking against Portuguese text is already precise at
  this scale, and there is no vector leg to hybridize with. Adding
  reranking here would be complexity without a measured benefit — this
  session's real eval run (`docs/evaluation/baseline.md`) shows both
  retrieval-dependent cases (010, 011) scoring faithfulness 1.00, which is
  evidence the current retrieval is not the bottleneck.

**No changes made.**

## Context assembly

Reviewed: `src/rag_b3/generation/answer.py`. Tool results are injected
directly as `tool_result` content blocks — there is no separate
chunk-ranking/deduplication/token-budget pass, because tool results here are
small, structured JSON (one bar, one summary, up to 5 CVM items) rather than
free-text chunks that could blow a context budget. The 5-round tool-use cap
(`MAX_TOOL_ITERATIONS`) is the only budget control, and it bounds worst-case
latency/cost rather than context size specifically. Given the measured token
counts this session (mean ~5,100 input tokens per generation call, see
`docs/evaluation/baseline.md`), context size is nowhere near a real
constraint for this system's current scope.

**No changes made.**

## Generation

Reviewed: `src/rag_b3/generation/{prompt.py,answer.py,tools.py,client.py}`.

- System prompt enforces grounding (never compute/recall, always call a
  tool), mandatory citation fields (`trade_date`, `source` for numeric;
  title/date/link for CVM), and explicit refusal domains (individual stock
  quotes, investment advice, future predictions).
- No forced JSON schema on the final answer (free text) — deliberate,
  since the answer is meant to read naturally in a chat UI; structured
  output *is* enforced on tool calls (JSON Schema `input_schema`) and on
  the eval judge (forced `tool_choice`).
- **Change made this session (additive only):** `AnswerResult` now carries
  `input_tokens`, `output_tokens`, `api_calls`, `latency_seconds`,
  `model_id` — real, previously-uncaptured engineering metrics, read from
  `response.usage`/`response.model`. This required no change to the tool-use
  loop's control flow, grounding logic, or prompt — verified by the full
  existing test suite passing unchanged (plus new assertions on the new
  fields). See `docs/evaluation/methodology.md` for the full rationale.

## Summary

| Sub-area | Changed this session? | Why |
|---|---|---|
| Ingestion | No | Already solid; no P0/P1 findings |
| Chunking | N/A | Correctly absent by design |
| Embeddings | N/A | Correctly absent by design |
| Retrieval | No | Reviewed, reranking/hybrid confirmed unnecessary at this scale |
| Context assembly | No | Reviewed, no token-budget risk at current scale |
| Generation | Yes (additive) | Added engineering-metrics capture, required for Phase 3/10 evaluation and observability work — no behavioral change to grounding/generation logic |
