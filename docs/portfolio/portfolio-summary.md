# Portfolio Summary

## What this project is

A production-oriented (not production-ready — no real deployment exists,
see below) RAG/LLM application answering questions about the Ibovespa
index and CVM regulatory announcements, built and hardened across a
7-session engineering process: audit → RAG pipeline review → evaluation →
regression testing → tool-calling security → observability → testing/CI/CD
→ system design and ADRs → this README/portfolio pass.

## Why it exists

Built as a case study for a Product Manager → AI Engineer career
transition — the goal was to take a working prototype and apply the same
engineering discipline a professional AI engineering team would: measure
before optimizing, document decisions with alternatives and trade-offs,
build executable tests instead of prose claims, and report gaps honestly
instead of hiding them.

## What's real and verifiable

Every claim in this project's documentation is backed by something a
reviewer can check directly:

- **166 tests**, 151 runnable without any API cost, all passing.
- **A real evaluation baseline** (0.909-0.935 faithfulness, 0.973-0.977
  relevancy) from persisted JSON artifacts, not narrative claims.
- **Two real security vulnerabilities** found and fixed via executable
  adversarial tests, with the vulnerable-then-fixed code both visible in
  git history.
- **A real production incident** (the Sonnet→Haiku→Sonnet model
  regression) with root cause, timeline, and a regression check proven via
  unit test to catch it.
- **A working CI pipeline** (locally validated end-to-end; not yet
  verified against a real GitHub Actions run — stated explicitly, not
  implied).
- **A real cost model** (~US$0.013/request, derived from actual token
  counts).

## What this project is not

- **Not deployed publicly.** Runs locally/via Tailscale by deliberate
  choice (`docs/adr/ADR-008-deployment.md`) — the engineering artifact is
  the deliverable here, not a live URL.
- **Not "production-ready."** No authentication, no rate limiting, an
  18-error mypy baseline left unfixed, a 2-run (not statistically robust)
  regression baseline. All stated plainly in
  `docs/audit/TECHNICAL_AUDIT.md` and this README's Roadmap section, not
  glossed over.
- **Not a vector-RAG showcase.** The retrieval architecture deliberately
  uses SQL and full-text search instead — a considered decision
  (`docs/adr/ADR-002-rag-architecture.md`), not a shortfall relative to
  what "RAG" usually means.

## Who should read what

- **A quick technical overview**: [`README.md`](../../README.md).
- **The single best interview story**: [`docs/evaluation/model-regression-case-study.md`](../evaluation/model-regression-case-study.md).
- **Depth on any specific competency**: `docs/technical-highlights.md` in
  this same directory maps each AI-engineering skill area to its concrete
  evidence in the repo.
- **Practicing for an actual interview**: `docs/interview-guide.md`.
