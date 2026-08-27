# Implementation Progress — RAG_Finance_IBOV Flagship Transformation

Living tracker across the 8-session execution plan. Updated at the end of each session.

## Session map (roadmap phases → sessions)

| Session | Scope (original 20-phase roadmap) |
|---|---|
| 1 | Auditoria completa → `TECHNICAL_AUDIT.md` → plano P0/P1/P2 |
| 2 | RAG Pipeline (Phase 2) + Evaluation (Phase 3) |
| 3 | Regression Testing (Phase 4) + Golden Dataset + Model Regression case study (Phase 5) |
| 4 | Tool Calling (Phase 6) + AI Security (Phase 7) + App Security (Phase 8) |
| 5 | Observability (Phase 9) + Cost & Performance (Phase 10) |
| 6 | Testing (Phase 11) + Docker (Phase 12) + CI/CD (Phase 13) |
| 7 | Deployment (Phase 14) + System Design (Phase 15, incl. ADRs) |
| 8 | README (Phase 16) + Portfolio Positioning (Phase 17) + Final Validation (Phase 18) + Changelog (Phase 19) + Final Report (Phase 20) |

## Current phase

**Session 4 — Tool Calling + AI Security.** Status: complete.

## Completed

### Session 1 — Technical Audit

- [x] Read-only audit of the full repository via 3 parallel Explore agents (structure/config/
      Docker/CI; RAG pipeline/LLM/tool-calling; tests/evaluation/security/observability).
- [x] `docs/audit/TECHNICAL_AUDIT.md` written — architecture (with Mermaid diagrams), components,
      strengths, 15 problems with evidence, risk classification (security/performance/reliability),
      testing/evaluation/observability/deployment/documentation gaps, and a 23-item prioritized
      findings table (F-01..F-23, P0–P3).
- [x] Confirmed and documented the model regression case (Sonnet 0.899/0.973 → Haiku 0.767/0.963 →
      reverted to Sonnet 2026-08-24), with the important caveat that the post-revert 0.899 figure is
      unverified and no raw eval output is persisted anywhere (F-03, F-04).
- [x] Flagged the core architectural framing correction: this is SQL tool-calling + Postgres
      full-text search, not vector-embedding RAG — a deliberate, documented, defensible decision
      (not a defect), but the README currently oversells the "RAG" label.

### Session 2 — RAG Pipeline + Evaluation

- [x] Verified `JUDGE_MODEL = "claude-opus-4-8"` and `claude-sonnet-5` live against the real
      Anthropic API — both valid (F-08 resolved).
- [x] Added real engineering-metrics capture: `AnswerResult.{input_tokens,output_tokens,api_calls,
      latency_seconds,model_id}` in `src/rag_b3/generation/answer.py`; judge token usage in
      `src/rag_b3/eval/judge.py`/`models.py`; cost estimation in `src/rag_b3/common/pricing.py`
      (explicit price table, returns `None` rather than guessing for unknown models). All additive,
      backward-compatible — full existing suite still passes, plus new tests.
- [x] Added a global FastAPI exception handler (`web/app.py`) — unhandled exceptions now log full
      detail server-side and return a generic 500 to the client (no internal detail leakage);
      added per-request summary logging on `POST /api/ask` (no query/answer content logged).
- [x] Extended `scripts/run_eval.py` to persist every run as a timestamped JSON artifact under
      `docs/evaluation/results/`, including per-case and aggregate engineering metrics.
- [x] Started Docker (`docker compose up -d`), confirmed real data present (`ibov_daily_history`
      2,644 rows 2016-01-04→2026-08-24; `cvm_feed_item` 60 rows).
- [x] **Re-ran `scripts/run_eval.py` for real** — reconfirmed baseline: faithfulness 0.909,
      relevancy 0.973, 0% error rate, gate PASSED. Closes F-04 (baseline was previously unverified
      post-revert) and F-03 (results now persisted). See `docs/evaluation/baseline.md`.
- [x] Documented methodology (`docs/evaluation/methodology.md`), including an honest limitation
      write-up for retrieval P@K/R@K/MRR (F-21: not computable reliably without a frozen corpus
      snapshot to hand-label against — documented rather than fabricated) and a real, non-obvious
      finding (a systematic judge-flagged "unsupported claim" caused by a disclosure sentence the
      system prompt requires but that isn't literally present in tool-call context).
- [x] Wrote `docs/architecture/{overview,data-flow,rag-pipeline,ai-architecture,deployment}.md` —
      Phase 1 deliverable, folded into this session as a natural prerequisite for the Phase 2 review.
- [x] Deep-dive pipeline review (Phase 2): ingestion, chunking (N/A by design), embeddings (N/A by
      design), retrieval, context assembly, generation — all reviewed against the audit's findings;
      confirmed no code changes warranted beyond the additive metrics capture above (preservation
      rule respected — nothing rewritten without justification).
- [x] Updated `docs/audit/TECHNICAL_AUDIT.md` with a status-update table reflecting F-08/F-04/F-03
      resolved, F-05/F-06/F-17 partially or fully resolved this session.

### Session 3 — Regression Testing + Golden Dataset + Model Regression Case Study

- [x] Ran `scripts/run_eval.py` a second time for real (real API cost, ~US$0.74) to get a second
      calibration data point: faithfulness 0.935, relevancy 0.977 (vs. 0.909/0.973 from Session 2's
      run) — both PASS.
- [x] Attempted a third calibration run — **blocked**: Anthropic API returned `400
      invalid_request_error: Your credit balance is too low to access the Anthropic API`. Reported
      honestly rather than hidden or worked around; see "Blocked" below. **This blocks all further
      real-LLM-call work (llm_eval tests, more eval runs, any future tool-calling/security testing
      that needs real API calls) until the user adds credit.**
- [x] Built `src/rag_b3/eval/regression.py` (testable comparison logic: baseline mean - tolerance,
      floored by the pre-existing hard gate 0.85/0.80) and `scripts/check_regression.py` (CLI
      wrapper comparing the latest persisted result against `docs/evaluation/baseline.json`).
- [x] Calibrated `docs/evaluation/baseline.json` from the 2 real runs (mean faithfulness 0.922,
      stdev 0.018; mean relevancy 0.975, stdev 0.003) — tolerance set conservatively (~3x stdev)
      and explicitly marked `n=2`/provisional, with a recommendation to recalibrate once ≥5 runs are
      affordable.
- [x] Added `tests/unit/test_eval_regression.py` — proves, using the actual historical Haiku
      regression numbers (0.767/0.963) fed through the real check logic, that the regression check
      would have caught that exact incident. Also proves it does NOT false-positive on the 2 real
      Sonnet runs, and that it catches a sub-hard-floor-but-above-relative-tolerance case the
      absolute gate alone would miss.
- [x] Wrote `docs/evaluation/regression.md` — full methodology, including the honest n=2 limitation.
- [x] Wrote `docs/evaluation/model-regression-case-study.md` — full Sonnet→Haiku→Sonnet narrative,
      timeline, root cause, and what this session added (independent reconfirmation + a working,
      unit-tested regression check) — addresses roadmap Phase 5 in full.
- [x] Updated `docs/evaluation/baseline.md` to reflect both calibration runs and link
      `baseline.json`.
- [x] Considered golden dataset's unused `last_passed` field — confirmed via repo-wide grep it's
      read by no code anywhere; deliberately left unchanged (not a P0/P1 issue, and wiring it up
      would mean deciding a new behavior, which is out of this session's scope) — noted for a
      future session if ever prioritized.
- [x] Updated `docs/audit/TECHNICAL_AUDIT.md` status table: F-02 now "logic built, not yet
      CI-wired" (CI itself remains Session 6 scope, F-01 still open).

### Session 4 — Tool Calling + AI Security

- [x] Wrote `docs/ai/tool-calling.md` — full audit of all 9 tools (purpose, schema, validation,
      authorization, timeout/retry, error handling, cost, security risk per tool).
- [x] **Found and fixed a real bug**: `cvm_search`/`cvm_latest_by_feed`'s `limit` parameter had no
      upper bound anywhere (schema declared bare `integer`, no clamp in the retrieval functions) —
      a malformed/manipulated model call could request an unbounded result set. Fixed with
      `_clamp_limit()` in `src/rag_b3/retrieval/cvm_textual.py` (`[1, 50]`), covered by new
      integration tests.
- [x] Wrote `tests/security/` (new directory): `test_tool_allowlist.py` (proves unknown/adversarial
      tool names never execute, structurally verifies no tool grants write/shell/network
      capability), `test_injection_resistance.py` (SQL-injection-style and oversized payloads fed
      through the real `execute_tool` dispatch against real Postgres), `test_system_prompt_guardrails.py`
      (regression guard on the system prompt's grounding/refusal rules).
- [x] **Found and fixed a second real bug** while writing the injection-resistance tests: a NUL
      byte (`\x00`) in tool input raised `psycopg.DataError`, an unhandled exception that broke the
      tool's `{"error": ...}` contract and would surface as a raw 500 instead of letting the model
      recover. Fixed: `execute_tool` now catches `psycopg.DataError`, rolls back the connection
      defensively, returns a normal tool error.
- [x] Wrote `docs/security/AI_SECURITY.md` — all 10 threat categories (attack/impact/likelihood/
      mitigation/test), grounded in this system's actual scope rather than a generic checklist.
      Both real findings from this session are documented with their fixes and tests.
- [x] Wrote `docs/security/APP_SECURITY.md` — authn/authz, CORS, secrets, SQL injection, input
      validation, rate limiting, dependency scanning, insecure defaults, error leakage, logging.
- [x] Fixed F-13: added `HOST`, `PORT`, `WATCHLIST_PATH`, `TIMEZONE` to `.env.example` (previously
      undocumented despite being functionally relevant — `HOST` in particular controls whether the
      unauthenticated app is reachable beyond localhost).
- [x] Added `pip-audit` as a dev dependency and ran it for real: **"No known vulnerabilities
      found"** (F-09 — tooling exists and was run; CI wiring remains Session 6).
- [x] Updated `docs/audit/TECHNICAL_AUDIT.md` status table with all of the above.

## In progress

- None. Session 4 scope is closed.

## Blocked

- **Anthropic API billing/credit limit reached** (encountered 2026-08-27 during Session 3's third
  calibration run attempt). Any further work requiring real LLM API calls — additional eval
  calibration runs, `llm_eval`-marked tests, Session 4's planned adversarial/security testing
  against the real model — is blocked until the user adds credit. Non-API-cost work (security
  review of existing code/config, Docker, CI/CD scaffolding, documentation, ADRs, README) is
  unaffected and continues.

## Key decisions made this session

- Docker Desktop was not running at session start; started it and `docker compose up -d` to get a
  real Postgres with real data for the eval re-run, rather than skipping/mocking this step.
- Judge/generation token-usage capture uses `getattr(response, "usage"/"model", ...)` defensively
  so it never breaks on a test mock that doesn't simulate these fields — verified via updated unit
  tests, not just by inspection.
- Retrieval Precision@K/Recall@K/MRR deliberately NOT computed this session — documented as a real
  limitation (no stable ground-truth relevant-set against a live-updating CVM feed) rather than
  fabricated against golden-dataset fields that don't actually support it.
- `docs/evaluation/regression.md` (tolerance bands, CI gate logic) deliberately deferred to
  Session 3 — this session only establishes and persists the baseline; setting thresholds before
  having a real baseline would violate the project's own "measure first" rule.
- Session 4: chose to fix the `limit` clamp and `psycopg.DataError` bugs immediately upon finding
  them (rather than only documenting them for a later session) since both were small, well-scoped,
  directly tied to the security review being written, and easily covered by tests written in the
  same pass — consistent with "preserve working code, fix what's actually broken with justification."
- Session 4: `tests/security/conftest.py` duplicates the small `conn` fixture from
  `tests/integration/conftest.py` rather than restructuring the existing conftest hierarchy — a
  deliberate minimal-footprint choice over consolidating into a shared root fixture.
- Session 4: true adversarial *LLM* resistance testing (does the live model actually resist a novel
  injection payload) was not attempted given the API credit blocker — only structural/mocked tests
  and analysis of the existing golden-dataset adversarial results were done. This is reported as an
  honest scope limitation in `docs/security/AI_SECURITY.md`, not glossed over.

## Next steps (Session 5 — Observability + Cost & Performance)

1. Still blocked on real LLM calls (API credit) — Session 5's scope (observability, cost/latency
   measurement) is mostly non-API-cost work: it's about instrumenting and documenting what Session
   2 already started capturing (`AnswerResult` tokens/latency, `/api/ask` logging), not making new
   LLM calls.
2. Write `docs/observability.md` — what's monitored today (API request logging, ingestion audit
   trail, the eval/regression artifacts) vs. what Phase 9 originally asked for (live metrics
   dashboards, retrieval-specific latency, LLM failure/retry/fallback tracking) — most of the latter
   still doesn't exist and should be honestly scoped, not overstated.
3. Consider whether the existing per-request log line (Session 2) is sufficient "observability" or
   whether a lightweight metrics store (e.g., writing request summaries to a table, similar to
   `ingestion_job_run`) is worth adding — weigh against the project's actual single-user scale
   before building something unused.
4. Cost & performance (Phase 10): the pieces already exist (token counts, latency, cost estimation
   in `docs/evaluation/methodology.md`/`pricing.py`) — this session's job is to extend that from
   "eval-run-only" to "every real chat request," and to write up bottleneck analysis using the real
   numbers already measured (mean ~7.25s generation latency, ~5,100 input tokens/request) rather
   than guessing at bottlenecks.
5. Revisit whether `generation/answer.py`/`tools.py` need actual `logging` calls (not just the
   web-layer summary log added in Session 2) — the audit's F-06 is only partially resolved.

## Test/validation runs performed

| Date | Command | Result |
|---|---|---|
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 1, audit agent, read-only) | 88 passed, 42 deselected |
| 2026-08-27 | `.venv/bin/python -m pytest --collect-only -q -m ""` (Session 1, audit agent) | 130 collected |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 2, after engineering-metrics changes) | 92 passed, 42 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 2) | All checks passed |
| 2026-08-27 | `.venv/bin/python -m pytest -q -m integration` (Session 2, real Postgres) | 27 passed |
| 2026-08-27 | `.venv/bin/python scripts/run_eval.py` (Session 2, real API — real cost ~US$0.74) | faithfulness 0.909, relevancy 0.973, 0% errors, GATE: PASSOU |
| 2026-08-27 | `.venv/bin/python scripts/run_eval.py` (Session 3, real API — real cost ~US$0.74) | faithfulness 0.935, relevancy 0.977, 0% errors, GATE: PASSOU |
| 2026-08-27 | `.venv/bin/python scripts/run_eval.py` (Session 3, 3rd attempt) | **BLOCKED**: `400 invalid_request_error: Your credit balance is too low` |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 3, after regression-check changes) | 98 passed, 42 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 3) | All checks passed |
| 2026-08-27 | `.venv/bin/python scripts/check_regression.py` (Session 3, no API cost — reads persisted JSON) | REGRESSION CHECK: PASSOU |
| 2026-08-27 | `.venv/bin/python -m pytest -q -m integration` (Session 4, real Postgres, incl. new security tests) | 37 passed |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 4, after tool/security fixes) | 110 passed, 52 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 4) | All checks passed |
| 2026-08-27 | `.venv/bin/pip-audit --desc` (Session 4) | No known vulnerabilities found |
