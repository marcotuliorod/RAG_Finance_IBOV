# ADR-005: Tool Calling Design

## Status

Accepted, hardened Session 4.

## Context

The LLM needs a way to fetch real data instead of answering from
parametric memory (the system's core grounding requirement — see
ADR-002/ADR-003). This ADR covers how tool access is scoped and secured,
not what the tools query (that's ADR-003).

## Decision

- **9 tools, all read-only**, dispatched through a closed `if/elif` chain
  in `execute_tool` (`src/rag_b3/generation/tools.py`) — not a dynamic
  lookup, not `eval`/`getattr` on the tool name. An unrecognized tool name
  returns `{"error": "ferramenta desconhecida: ..."}` rather than
  executing anything.
- **Two validation layers**: the Anthropic-enforced JSON Schema, plus
  independent allowlist/bounds checks in the query/retrieval layer itself
  (defense in depth — the schema alone isn't trusted).
- **Errors become tool results, not exceptions**: `InsufficientDataError`,
  `ValueError`, and (added Session 4) `psycopg.DataError` are all caught
  and converted to `{"error": ...}` so the model can see the failure and
  respond honestly ("dado insuficiente") instead of the request failing
  outright.

## Alternatives considered

| Option | Why not chosen |
|---|---|
| One generic SQL-execution tool | Rejected — see ADR-003; would remove the allowlist-by-construction property that makes "excessive agency" a non-issue for this system (`docs/security/AI_SECURITY.md` §5). |
| Write/mutation tools (e.g., letting the model trigger a re-ingestion) | Never built — no user-facing need justifies giving the model write access, and every AI-security threat category analyzed is meaningfully lower-severity specifically because no write path exists. |
| Trusting the JSON Schema alone for input validation | Rejected after finding a real gap this session: `limit` had no upper bound anywhere despite the schema declaring it as a plain integer — fixed with a second, code-level clamp (`_clamp_limit`, `src/rag_b3/retrieval/cvm_textual.py`). |

## Trade-offs

The closed `if/elif` dispatch doesn't scale elegantly to a much larger
number of tools (a registry/decorator pattern would be more extensible),
but at 9 tools the explicit chain is easy to audit in full — which mattered
more here, given `docs/ai/tool-calling.md`'s audit was written by reading
every branch directly.

## Consequences

- Adding a new tool means adding both a `TOOL_SPECS` entry and an
  `execute_tool` branch — a small amount of duplication, but it keeps the
  full tool inventory auditable at a glance (verified in
  `tests/security/test_tool_allowlist.py`, which asserts the *exact* set of
  9 tool names and checks no tool description implies write/shell/network
  capability).
- Two real bugs were found and fixed via this design's testability
  (unbounded `limit`, unhandled `psycopg.DataError`) — evidence that the
  closed, auditable dispatch made these findable in the first place.
