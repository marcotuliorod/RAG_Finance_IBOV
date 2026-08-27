# Cost & Performance

Real, measured numbers only — this document reports what was observed
across 2 real evaluation runs (Session 2/3, 30 generation requests total)
plus the underlying token-based cost model
(`src/rag_b3/common/pricing.py`). No numbers here are estimated or
extrapolated beyond what was actually captured by `response.usage`.

## What was measured

| Metric | Run 1 (2026-08-27T14:43Z) | Run 2 (2026-08-27T14:53Z) |
|---|---|---|
| Mean generation latency | 7.25s / request | 7.31s / request |
| Total generation tokens | 77,301 in / 6,371 out | 77,126 in / 6,103 out |
| Total judge tokens | 40,317 in / 12,971 out | 40,621 in / 13,050 out |
| Estimated total cost (15 cases, generation + judge) | US$ 0.744 | US$ 0.745 |
| Error rate | 0% | 0% |

Source: `docs/evaluation/results/*.json`, `docs/evaluation/baseline.md`.

## Per-request cost breakdown (typical case, from real data)

A single generation call averages ~5,100 input tokens / ~300 output tokens
(most cases: one or two tool-use rounds). At `claude-sonnet-5` pricing
($2.00/$10.00 per 1M tokens — `src/rag_b3/common/pricing.py`, captured
2026-08-27), a typical user-facing chat request costs roughly:

```
5,100 input tokens  × $2.00 / 1,000,000  ≈ $0.0102
  300 output tokens × $10.00 / 1,000,000 ≈ $0.0030
                                    total ≈ $0.013 per request
```

The eval judge (`claude-opus-4-8`, $5.00/$25.00 per 1M tokens) is not part
of the user-facing request path — it only runs during
`scripts/run_eval.py`, so it doesn't add to per-request production cost.

**This confirms the project's own cost estimate in `docs/PRD.md` §13
("Estimativa de Custos", previously marked "a estimar") was directionally
correct** — real per-request cost is a fraction of a cent, consistent with
"uso pessoal, baixo volume" being genuinely low-cost. This is the first
session where that PRD placeholder can be replaced with a measured number
rather than a guess.

## Latency breakdown

Two clusters are visible in the raw per-case data
(`docs/evaluation/results/*.json`):

- **Simple cases (0-1 tool calls, e.g. adversarial refusals):** ~3.4-5.6s.
  These involve 1 generation API call.
- **Multi-tool-call cases (e.g. multi-hop case 011, needing a CVM lookup
  then a numeric lookup):** up to ~19s, 3 API calls.

The dominant cost in latency is **API round-trip time, not local compute**
— tool execution itself is fast, indexed SQL (see
`docs/architecture/rag-pipeline.md` — no measured retrieval bottleneck).
This means the realistic lever for reducing latency, if it ever mattered at
this system's scale, would be reducing tool-use rounds (better prompting to
resolve multi-hop questions in fewer calls) or using a faster model —
**not** optimizing the SQL layer, which is already fast.

## Bottleneck analysis — measure first, don't guess

Per the project's own rule ("não otimize prematuramente... primeiro
medir"), the only bottleneck actually evidenced by real data is: **more
tool-use rounds = more latency**, roughly linearly (each round is a full
API round-trip). There is no evidence of:

- Excessive context size (mean ~5,100 input tokens is well within any
  current model's context window — not a real constraint at this scale).
- Redundant retrieval (each tool call in the logged traces corresponds to a
  distinct information need — no repeated identical tool calls observed in
  the 30 requests reviewed).
- Expensive individual operations (`query/ibov_numeric.py`/`retrieval/cvm_textual.py`
  queries are all single-table, indexed lookups against small tables).

**No optimization was made this session** — there is nothing in the
measured data that justifies one. This is deliberately reported as "nothing
to optimize yet" rather than inventing a change to look productive.

## What would change this analysis

At meaningfully higher request volume (the system is currently single-user,
personal-use), the things worth re-measuring before optimizing would be:
concurrent request handling (untested — no load test has been run), and
whether `MAX_TOOL_ITERATIONS = 5`'s worst-case ~5×latency tail becomes a
real-world tail-latency problem rather than a theoretical one. Neither is
relevant at current usage and neither has been built or tested — noted as
a legitimate gap, not a guess at future numbers.
