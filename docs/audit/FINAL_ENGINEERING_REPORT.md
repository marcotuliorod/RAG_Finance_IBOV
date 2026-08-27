# Final Engineering Report

**Scope:** the 8-session flagship-project transformation of RAG_Finance_IBOV,
executed 2026-08-27. **Method:** every claim below is backed by a specific
file, test, or persisted artifact in this repository — cross-references are
given throughout rather than asserted from memory.

## Before

At the start of Session 1 (`docs/audit/TECHNICAL_AUDIT.md`, full detail):

- No CI/CD of any kind (`.github/` didn't exist).
- Only Postgres containerized — `docker compose up` didn't start the app.
- Zero token/cost/latency tracking anywhere in the generation path, despite
  `response.usage` being available on every Anthropic API call.
- Zero logging in the web/generation layers.
- Evaluation results existed only as hand-typed prose in 4 different
  markdown files — no run had ever been persisted as a machine-readable
  artifact.
- The post-Haiku-revert faithfulness baseline (0.899) was never
  reconfirmed — the docs themselves said so.
- `JUDGE_MODEL = "claude-opus-4-8"` had never been independently verified
  against the live API.
- Migrations had no tracking table — unsafe to re-run.
- No dependency vulnerability scanning.
- No dedicated security test suite.
- No ADRs, system design docs, or architecture documentation.
- README had two stale claims (test-count badge, a Haiku/Sonnet narrative
  describing a regression as "kept" when it had actually been reverted).
- 130 tests existed (88 unit + 42 integration/eval).

## After

- **20 commits** across 8 sessions, each scoped and independently
  reviewable (`git log`).
- **166 tests** (up from 130): 112 unit, 39 integration/e2e/security (all
  free to run), 15 `llm_eval` (real API cost, gated).
- **2 real security vulnerabilities found and fixed** via executable
  adversarial tests: an unbounded tool `limit`, and an unhandled
  `psycopg.DataError` on malformed input.
- **A real, artifact-backed evaluation baseline**: faithfulness
  0.909-0.935, relevancy 0.973-0.977, 0% error rate, across 2 independently
  re-run evaluation passes (`docs/evaluation/results/*.json`).
- **A working regression check**, unit-tested against the actual
  historical Haiku regression numbers and proven to catch that exact
  incident (`tests/unit/test_eval_regression.py`).
- **The app is fully containerized** (`Dockerfile` + `docker-compose.yml`),
  verified end-to-end locally (build → up → both services healthy → real
  data visible over the Docker network).
- **CI/CD exists**: `.github/workflows/ci.yml` (lint, mypy, unit,
  integration, security, `pip-audit`, Docker build) and
  `.github/workflows/eval.yml` (real evaluation + regression gate, manual/
  scheduled given real cost).
- **A real-data seed fixture** (`db/seed/`) makes CI's fresh-database jobs
  actually pass — a gap discovered and fixed during this session, not left
  for CI's first real run to surface.
- **Idempotent migrations** — verified against both the real dev database
  and a fresh throwaway container.
- **`pip-audit` clean** — zero known dependency vulnerabilities as of the
  last scan, now running on every CI push.
- **8 ADRs, 6 system-design docs, full AI/app security reviews, a
  deployment strategy comparing 5 real options** — all in `docs/`.
- **README rewritten** (English + Portuguese), correcting both stale
  claims found in the audit and the "RAG" framing.

## Architecture

Final shape documented in `docs/architecture/overview.md` and
`docs/system-design/architecture.md`: a FastAPI app orchestrating a
Claude tool-use loop over 9 read-only tools (SQL for the numeric index,
Postgres full-text search for CVM regulatory content), backed by 4
independent, retry-hardened ingestion pipelines. No vector embeddings —
a deliberate, now-formalized decision (`docs/adr/ADR-002-rag-architecture.md`),
re-validated against real evaluation data rather than left as an
unquestioned inheritance from the original build.

## Testing

| Tier | Count | Cost |
|---|---|---|
| Unit | 112 | Free |
| Integration + E2E + Security | 39 | Free (needs local Postgres) |
| AI Evaluation | 15 | Real, billed API calls |
| **Total** | **166** | |

All 151 free tests pass. The 15 `llm_eval` tests could not be freshly
re-verified in later sessions due to an Anthropic API billing limit reached
mid-project (Session 3) — their last known-passing state is the 2 real
evaluation runs from Sessions 2-3, both of which passed the quality gate.

## Evaluation

Baseline (`docs/evaluation/baseline.md`): faithfulness 0.909 and 0.935
(mean 0.922) across two independent real runs, relevancy 0.973 and 0.977
(mean 0.975), both comfortably above the project's 0.85/0.80 gate. The
regression check (`docs/evaluation/regression.md`) is calibrated from these
2 runs — explicitly flagged as a thin sample (n=2), with a stated
recalibration plan for when more API budget is available, rather than
presented as more statistically confident than it is.

## Security

10-threat-category AI security review plus a full application security
review (`docs/security/`). Two real vulnerabilities found and fixed this
session via executable tests, not review alone. The most significant
structural mitigation — a fully read-only tool surface, meaning
"excessive agency" is architecturally absent rather than merely mitigated
— predates this session but is now formally documented and tested
(`tests/security/test_tool_allowlist.py`).

**Known, stated security gaps**: no authentication (deliberate, scoped
decision — `docs/adr/ADR-007-security.md`), no rate limiting, no
structural prompt-injection defense (prompt-level only).

## Observability

Structured per-request logging (never logging query/answer content), a
global exception handler that never leaks internal detail, and persisted
evaluation artifacts. No live dashboard or tracing — a stated scope
decision for a single-user system (`docs/adr/ADR-006-observability.md`),
not an unexamined gap.

## CI/CD

Two workflows: `ci.yml` (every push/PR — lint, mypy non-blocking against a
measured 18-error baseline, unit/integration/security tests, `pip-audit`,
Docker build) and `eval.yml` (manual + weekly schedule — the real, billed
evaluation and regression gate).

**Update — verified against real GitHub Actions post-project**: the
project owner authorized pushing and opening
[PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1). `ci.yml`
ran for real; all 6 jobs passed. The first real run surfaced a genuine bug
local simulation had missed: `astral-sh/setup-uv@v3` silently ignores an
unsupported `python-version` input (that's `actions/setup-python`'s
interface), so the intended Python 3.12 pin was never actually applied.
Fixed with a standard `.python-version` file; a second real run confirmed
all 6 jobs passing cleanly, with the `python-version` warning gone and the
mypy non-blocking design (step fails, job still passes) confirmed working
exactly as intended. `eval.yml` has not yet been triggered for real — it
needs an `ANTHROPIC_API_KEY` repository secret configured first, which
remains a follow-up item.

## Deployment

Containerized and locally verified, but **not deployed anywhere**. The
deployment strategy (`docs/deployment/strategy.md`,
`docs/adr/ADR-008-deployment.md`) recommends staying local + a private
mesh network (Tailscale) over a cloud deployment, explicitly weighing that
this project already hit one free-tier resource-limit wall (the original
Supabase migration) and judging that a single-user tool's portfolio value
doesn't require repeating that risk.

## Remaining Gaps

Stated plainly, per the project's own ground rules against hiding
limitations:

1. **No rate limiting** on `/api/ask` (F-11).
2. **18 pre-existing mypy errors**, measured and CI-visible but not fixed —
   judged out of proportion to fix without a concrete bug driving it.
3. **Regression baseline is n=2** — needs recalibration with ≥5 runs once
   more API budget is available.
4. ~~CI workflows unverified against real GitHub Actions~~ — **resolved
   post-project**: `ci.yml` now verified passing on two real runs
   ([PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1)).
   `eval.yml` still hasn't run for real (needs an `ANTHROPIC_API_KEY`
   secret configured in the repo) — a smaller, remaining piece of this gap.
5. **Retrieval-quality metrics (Precision@K/Recall@K/MRR) unmeasured** —
   no reliable ground truth exists against the live-updating CVM feed
   without building a frozen-snapshot fixture, which wasn't done.
6. **The Anthropic API billing/credit limit reached in Session 3** means
   no further real-LLM-call adversarial testing, calibration runs, or
   `llm_eval` re-verification happened after that point — a real
   constraint on how much of this session's later work could be
   empirically re-validated against the live model, not just against
   mocked/structural tests.
7. **No public deployment** — by choice (see Deployment above), but worth
   restating as a gap relative to the original brief's aspiration for a
   demonstrable live system.

## Portfolio Value

This project now demonstrates, with verifiable evidence rather than
claims: RAG architecture decision-making (with a documented, defensible
non-default choice), LLM evaluation methodology (a real regression
incident, caught and automated against), tool-calling security (2 real
bugs found via executable testing), AI and application security review,
observability and cost measurement grounded in real data, a tiered test
suite with an explicit cost boundary, a working CI/CD pipeline with a
reasoned cost trade-off, Docker-based reproducibility (including a real
gap found and fixed during CI validation), system design communication
(concrete scaling/reliability/trade-off analysis), and 8 ADRs documenting
architectural decision-making with alternatives and consequences. The
single strongest artifact for an interview is
`docs/evaluation/model-regression-case-study.md` — a real production
incident with root cause, measured impact, and an automated regression
check proven (not just claimed) to prevent recurrence.
