# Changelog

All notable changes from the flagship-project engineering pass (2026-08-27,
Sessions 1-8). Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Entries grouped by session; each links to the relevant docs/commits rather
than repeating their full detail.

## Post-project — Full Validation + Real GitHub Flow

### Fixed
- `astral-sh/setup-uv@v3` was being passed an unsupported `python-version`
  input (that's `actions/setup-python`'s interface) — GitHub Actions
  silently tolerated it, so `ci.yml` still passed, but the intended Python
  3.12 pin was never actually applied. Found on the first real GitHub
  Actions run of this project's CI. Fixed with a standard `.python-version`
  file; re-verified passing on a second real run.

### Changed
- Pushed all 24 commits and opened
  [PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1) —
  `ci.yml` verified passing for real on GitHub Actions (6/6 jobs), not just
  locally simulated. Updated `README.md`/`README.pt-BR.md` and the audit
  docs to reflect this.

## Session 8 — README, Portfolio, Final Validation

### Added
- `README.md` (English) and `README.pt-BR.md` (Portuguese) — full rewrite
  as a technical landing page, fixing two stale claims the Session 1 audit
  found (test-count badge, the Haiku/Sonnet regression narrative) and
  correcting the "RAG" framing per ADR-002.
- `docs/portfolio/` — portfolio-summary.md, technical-highlights.md,
  interview-guide.md.
- This `CHANGELOG.md`.
- `docs/audit/FINAL_ENGINEERING_REPORT.md`.

## Session 7 — Deployment, System Design, ADRs

### Added
- `docs/deployment/strategy.md` — compared 5 deployment options against
  this system's real constraints; chose Tailscale-first with a VPS upgrade
  path, explicitly weighing the project's past Supabase free-tier-limit
  incident.
- `docs/adr/ADR-001` through `ADR-008` — LLM selection, RAG architecture,
  retrieval strategy, evaluation strategy, tool calling, observability,
  security, deployment.
- `docs/system-design/` — context, architecture, scalability, reliability,
  security, trade-offs.

## Session 6 — Testing, Docker, CI/CD

### Added
- `tests/e2e/` — real full-stack tests (FastAPI + real Postgres, mocked
  LLM call only).
- `tests/evaluation/README.md` documenting where evaluation tests actually
  live.
- `Dockerfile` (multi-stage, non-root, healthcheck) and a `docker-compose.yml`
  `app` service — the application is now containerized, not just Postgres.
- `db/seed/dev_seed.sql` — a real-data (public Ibovespa/CVM) snapshot fixture
  making CI's fresh-database jobs actually pass.
- `.github/workflows/ci.yml` — lint, mypy (non-blocking), unit, integration,
  security + `pip-audit`, Docker build, on every push/PR.
- `.github/workflows/eval.yml` — real evaluation + regression gate, manual/
  scheduled (not per-commit, given real API cost).
- `mypy` as a dev dependency; measured an 18-error baseline, documented
  rather than hidden or silently skipped.

### Fixed
- `scripts/apply_migrations.py` was not safely re-runnable (no tracking
  table) — added `schema_migrations`, verified against both the real dev
  database and a fresh throwaway container.

## Session 5 — Observability, Cost & Performance

### Added
- Logging in `generation/answer.py` (tool calls, tool errors, loop-exceeded)
  — previously zero logging in the generation layer.
- `docs/observability.md`, `docs/cost-performance.md`.

### Changed
- `docs/PRD.md` §13's placeholder cost estimate ("a estimar") replaced with
  a real measured figure (~US$0.013/request).

## Session 4 — Tool Calling, AI Security

### Added
- `docs/ai/tool-calling.md` — full per-tool audit.
- `docs/security/AI_SECURITY.md`, `docs/security/APP_SECURITY.md`.
- `tests/security/` — executable adversarial tests (tool allowlist,
  injection resistance, system-prompt guardrail regression guard).
- `pip-audit` as a dev dependency, run manually this session (CI wiring:
  Session 6).

### Fixed
- **Security**: `cvm_search`/`cvm_latest_by_feed`'s `limit` tool input had
  no upper bound anywhere — a manipulated model call could request an
  unbounded result set. Clamped to `[1, 50]`.
- **Security**: a NUL byte in tool input raised an unhandled
  `psycopg.DataError`, breaking the tool error-handling contract. Now
  caught and converted to a graceful `{"error": ...}` with a defensive
  transaction rollback.
- `.env.example` was missing `HOST`, `PORT`, `WATCHLIST_PATH`, `TIMEZONE`.

## Session 3 — Regression Testing, Golden Dataset, Model Regression Case Study

### Added
- `src/rag_b3/eval/regression.py`, `scripts/check_regression.py` — a
  two-tier regression gate (absolute floor + relative to a measured
  baseline), unit-tested against the actual historical Haiku regression
  numbers.
- `docs/evaluation/baseline.json`, `docs/evaluation/regression.md`,
  `docs/evaluation/model-regression-case-study.md`.

### Changed
- Ran a second real evaluation pass (faithfulness 0.935, relevancy 0.977)
  to calibrate the regression baseline from 2 real data points instead of
  1. A third calibration run was attempted and blocked by an Anthropic API
  billing/credit limit — reported, not hidden.

## Session 2 — RAG Pipeline Review, Evaluation

### Added
- Token/latency/cost capture: `AnswerResult.{input_tokens,output_tokens,api_calls,latency_seconds,model_id}`,
  judge-side token capture in `eval/judge.py`/`models.py`,
  `src/rag_b3/common/pricing.py`.
- Global FastAPI exception handler + per-request logging on `POST /api/ask`.
- `scripts/run_eval.py` now persists every run as a timestamped JSON
  artifact (`docs/evaluation/results/`) — previously only printed to
  stdout, no run had ever been saved.
- `docs/architecture/` (overview, data-flow, rag-pipeline, ai-architecture,
  deployment), `docs/evaluation/methodology.md`, `docs/evaluation/baseline.md`.

### Changed
- Live-verified both `claude-sonnet-5` (generator) and `claude-opus-4-8`
  (judge) model identifiers against the real Anthropic API.
- Ran the first real evaluation pass with results actually persisted:
  faithfulness 0.909, relevancy 0.973 — reconfirming the post-Haiku-revert
  baseline for the first time (previously only the pre-Haiku prose number
  existed).

## Session 1 — Technical Audit

### Added
- `docs/audit/TECHNICAL_AUDIT.md` — full read-only audit (architecture,
  strengths, 15 problems with evidence, risk classification, testing/
  evaluation/observability/deployment/documentation gaps, 23-item
  prioritized findings table P0-P3).
- `docs/audit/IMPLEMENTATION_PROGRESS.md` — the session-by-session tracker
  this changelog is derived from.

### Found (not yet fixed at this point)
- The project's "RAG" framing oversold vector-embedding retrieval that
  doesn't exist — flagged as a decision to formalize (ADR-002), not a
  defect.
- Zero CI/CD, zero app containerization, zero cost/observability tracking,
  an unverified evaluation baseline, an unverified `JUDGE_MODEL` identifier
  — the full P0 list this changelog's later sessions worked through.
