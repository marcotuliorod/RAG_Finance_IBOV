# Interview Guide

Anticipated questions and grounded answers — each answer points to real
evidence in the repo, not just a talking point. Practice saying these out
loud, not just reading them.

## "Walk me through the architecture."

Start with the one-sentence version (README's Solution section), then
immediately volunteer the framing correction: *"despite the name, this
isn't vector-embedding RAG — retrieval is SQL for the numeric index and
Postgres full-text search for the regulatory feed. That was a considered
decision, not a shortcut — the corpus doesn't need approximate semantic
matching, it needs exact numbers."* Then reference
[ADR-002](../adr/ADR-002-rag-architecture.md) if pushed on why.

## "Why didn't you use embeddings / a vector database?"

The corpus is ~2,700 rows across two tables — a numeric time series (where
"close enough" is a worse failure mode than "insufficient data") and ~60
short regulatory items (where lexical `tsvector` search already performs
well). Adding pgvector or an external vector DB would be infrastructure
without a measured benefit. **Concrete trigger for revisiting**: if the CVM
source ever expanded from RSS summaries to full filing text (hundreds of
pages), that's when chunking + embeddings would likely become the right
call — stated explicitly in ADR-002, not left vague.

## "How do you know your RAG system doesn't hallucinate?"

Three layers, and be specific about each: (1) structural — all arithmetic
happens in SQL, there's no code path for the LLM to produce a number
without a tool call; (2) measured — faithfulness 0.909-0.935 across two
real evaluation runs, with the raw judge output (which claims were
supported/unsupported and why) persisted in
[`docs/evaluation/results/`](../evaluation/results/); (3) adversarial — 4
golden-dataset cases specifically probe refusal behavior (out-of-domain,
out-of-scope, insufficient-data, forecast-refusal), all scoring clean in
the real runs.

## "Tell me about a time a model change caused a real problem."

This is the strongest story in the project —
[`docs/evaluation/model-regression-case-study.md`](../evaluation/model-regression-case-study.md)
verbatim. Key beats: swapped to a cheaper/faster model for cost, measured
faithfulness drop from 0.899 to 0.767, root-caused it to the smaller model
skipping tool calls and using parametric memory, reverted, then — this is
the part that shows engineering maturity beyond "we noticed and fixed it"
— built an actual regression check and *proved with a unit test using the
real historical numbers* that it would catch the same incident
automatically next time.

## "How do you evaluate a RAG system? What metrics do you use?"

Two tiers: LLM-as-judge for generation quality (faithfulness — claim
decomposition against tool-call context; answer relevancy), and structural
verification for the numeric path (10 of 15 golden cases have a
deterministic resolver checked with zero LLM involvement). **Be ready for
the follow-up**: "what about retrieval metrics like Precision@K?" — the
honest answer is they're not computed, and *why* is a good answer, not a
gap to hide: no reliable ground-truth relevant-set exists against a
live-updating feed without freezing a snapshot to hand-label against
(`docs/evaluation/methodology.md`).

## "Why a custom LLM-as-judge instead of `ragas`/`deepeval`?"

`ragas==0.4.3`'s available version had a broken import
(`langchain_community.chat_models.vertexai`, removed upstream) that would
pull in an unwanted GCP dependency chain to fix. The technique (claim
decomposition + context-support checking) is the same; only the framework
dependency was avoided. Good follow-up if pushed: *"I'd revisit this if a
future `ragas` release fixes the import — I didn't reject the tool on
principle, I hit a concrete blocker."*

## "How do you secure tool calling for an LLM agent?"

Lead with the strongest point: **no write tools exist at all** — all 9
tools are read-only, so "excessive agency" isn't mitigated, it's
structurally absent. Then the two real bugs found via executable
adversarial testing (unbounded `limit`, unhandled malformed input) —
*"security testing found real issues specifically because the tests were
executable, not just a written threat model."*

## "What's your approach to prompt injection?"

Be honest about the gap here — it's a stronger answer than overclaiming.
*"Mitigation is prompt-level, not structural — I don't have a classifier or
guardrail model in front of this. That's an acceptable risk specifically
because the tool surface is read-only and scoped to public data — even a
fully successful injection can't cause data damage. I'd build a structural
defense before adding any write capability."*
([`docs/security/AI_SECURITY.md`](../security/AI_SECURITY.md) §1-2)

## "How do you handle observability/monitoring for an LLM app?"

Structured per-request logging (tokens, latency, tool calls — never
content), a global exception handler, persisted evaluation artifacts. Then
volunteer the scope reasoning: *"no live dashboard or tracing — for a
single-user system, that's infrastructure without a user. I documented the
specific trigger condition for building more (`docs/adr/ADR-006-observability.md`)
rather than either over-building or leaving it unexamined."*

## "What does this cost to run? How would you optimize it?"

~$0.013/request, measured from real token counts, not estimated. On
optimization: *"I looked for a bottleneck in the real request traces and
didn't find one worth fixing — latency is dominated by LLM API round-trip
time, not local compute, and reducing that means reducing tool-use rounds
via better prompting, not touching the SQL layer, which is already fast."*
Shows restraint against premature optimization, which is itself the
answer worth demonstrating.

## "How would this scale to more users?"

Specific, ordered list, not "we'd add more servers": connection pooling
first (currently one `psycopg.connect()` per request, no pool), then
caching for the numeric table (data changes at most daily, so it's
stale-safe to cache for hours), then rate limiting, then horizontal
scaling of the already-stateless FastAPI process
([`docs/system-design/scalability.md`](../system-design/scalability.md)).

## "Walk me through your CI/CD pipeline."

Lint → mypy (non-blocking, 18-error measured baseline) → unit tests →
integration tests (real Postgres service, real migrations, a seed fixture)
→ security tests + `pip-audit` → Docker build, on every push. Then the
interesting trade-off: *"evaluation isn't in that per-commit pipeline —
each real eval run costs ~$0.74 and takes minutes, so it's a separate
manual/scheduled workflow instead. That's a deliberate cost/coverage
trade-off, not an oversight."*

## "Is this production-ready?"

**No, and be specific about why, not defensive about it**: no
authentication, no rate limiting, a regression baseline calibrated from
only 2 runs, an unfixed mypy baseline, and the CI workflows have only been
locally simulated, never run against real GitHub Actions. *"It's
production-*oriented* — the practices (testing, evaluation, security
review, CI) are real and would extend cleanly to production use, but I
haven't done the specific hardening (auth, rate limiting) that only
matters once it's actually exposed beyond localhost, because it isn't."*

## "What would you do differently / what's still missing?"

Pull directly from the README's Roadmap section and
`docs/audit/TECHNICAL_AUDIT.md`'s open findings — having a memorized,
accurate list of real gaps is a stronger signal than claiming there are
none.
