# ADR-002: RAG Architecture — SQL + Full-Text Search, Not Vector Embeddings

## Status

Accepted (documented pre-existing decision, `docs/PRD.md`,
`.specify/memory/constitution.md`; formalized as an ADR in Session 7 after
Session 2's pipeline review re-confirmed it against real evaluation data).

## Context

"RAG" conventionally implies chunking + embeddings + vector similarity
search. This system's actual retrieval is two deterministic mechanisms
instead: parameterized SQL over a numeric time series, and PostgreSQL
native full-text search (`tsvector`) over a small, structured corpus. See
`docs/architecture/ai-architecture.md` for the full reasoning; this ADR
records it as a decision with alternatives and trade-offs.

## Decision

No embedding model, no vector store, no chunking pipeline. Retrieval is:

1. **Numeric**: exact SQL point/range queries against
   `ibov_daily_history` (`src/rag_b3/query/ibov_numeric.py`).
2. **Textual**: `tsvector`/`plainto_tsquery('portuguese', ...)` full-text
   search against `cvm_feed_item` (`src/rag_b3/retrieval/cvm_textual.py`),
   ~60 items.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| Embeddings + pgvector | The corpus doesn't need approximate/semantic retrieval — index values need to be exact, not "close enough," and 60 CVM items is small enough that lexical search performs well without the added infrastructure (extension, embedding model, embedding cost/latency, dimensionality decisions). |
| Embeddings + a dedicated vector DB (Pinecone/Chroma/FAISS) | Same reasoning as above, plus an additional external dependency/cost for a corpus this small. |
| `ragas` for the RAG-specific tooling ecosystem generally | Evaluated for the *evaluation* layer specifically (not retrieval) and rejected for an unrelated reason — a broken import in the available version (`docs/evaluation/methodology.md`) — not because RAG-specific tooling was rejected on principle. |

## Trade-offs

- **Gained**: retrieval correctness is exact for the numeric case (no
  approximate-match risk on financial figures), zero embedding
  cost/latency, one less infrastructure dependency (no vector extension or
  service), and — validated this session — genuinely strong measured
  faithfulness (0.909-0.935) partly *because* grounding is structurally
  guaranteed rather than approximated.
- **Given up**: this doesn't generalize. If the CVM corpus grew from RSS
  summaries to, say, full PDF filings running hundreds of pages, `tsvector`
  search would degrade and this decision would need revisiting — chunking
  + embeddings would likely become the right call at that point. This is
  explicitly a decision that fits *this* corpus's current shape, not a
  general claim that vector RAG is unnecessary.
- **No reranking or hybrid search** — evaluated as unneeded at 60 items
  (`docs/architecture/rag-pipeline.md`), re-confirmed by both
  retrieval-dependent golden dataset cases scoring faithfulness 1.00 in
  real evaluation runs.

## Consequences

- The system's name/framing ("RAG_Finance_IBOV") oversells the "RAG" label
  relative to what a reader would expect (vector RAG) — flagged in
  `docs/audit/TECHNICAL_AUDIT.md` §1 as something the eventual README
  rewrite (Session 8) needs to correct explicitly, not hide.
- This decision should be revisited if the CVM data source scope expands
  significantly (e.g., ingesting full filing text instead of RSS
  summaries) — noted here as the concrete trigger condition, not left
  vague.
