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

**Post-project follow-up — full validation + real GitHub flow.** Status: complete. The planned
8-session sequence (below) finished at Session 8; this follow-up executed the one item that
sequence explicitly left as a user decision: pushing to GitHub and verifying CI for real.

## Completed

### Post-project — Full validation + GitHub flow

- [x] Re-ran the complete local validation suite fresh: lint (clean), format check (same 21
      pre-existing files noted before, unchanged), mypy (18-error baseline, unchanged), unit tests
      (112 passed), integration/e2e/security tests (39 passed), `scripts/check_regression.py`
      (PASSOU, no new API cost), `pip-audit` (clean).
- [x] Ran the full `docker compose up` stack end-to-end again (alternate host port to avoid
      disrupting the user's already-running local process on 8000): both services healthy, app
      reached Postgres over the Docker network with real data (2,644/60 rows) visible, and —
      genuinely valuable extra evidence — hit `POST /api/ask` against the real container and
      confirmed the Session 2 global exception handler works correctly on a **real** failure (the
      known Anthropic billing block): full traceback logged server-side, only the generic
      `{"detail": "Erro interno do servidor."}` reached the client. Torn down and dev environment
      (port 8000, Postgres data) restored and confirmed intact afterward.
- [x] Pushed all 24 commits to `origin/chore/finalize-and-migrate-postgres` and opened
      [PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1) against `main` — the user
      explicitly asked for "o fluxo completo do GitHub" this turn, resolving the push decision that
      had been left pending at the end of Session 8.
- [x] **`ci.yml` ran for real on GitHub Actions for the first time** — all 6 jobs (lint, typecheck,
      unit-tests, integration-tests, security-tests, docker-build) passed on the first run.
- [x] **Found and fixed a real bug the first live run surfaced that local simulation had missed**:
      `astral-sh/setup-uv@v3` doesn't accept a `python-version` input (that's
      `actions/setup-python`'s interface) — GitHub Actions silently tolerates unknown inputs, so the
      job still passed, but the intended Python 3.12 pin was never actually being applied. Fixed
      with a standard `.python-version` file (which `setup-uv` respects automatically) and removed
      the ineffective input from every `setup-uv` step in both `ci.yml` and `eval.yml`.
      Pushed the fix; **re-ran CI for real a second time and confirmed all 6 jobs pass cleanly**,
      with the `python-version` warning gone from the run's annotations.
      Also confirmed, in the same real run's annotations, that the mypy step fails as expected
      (18-error baseline) but `continue-on-error: true` correctly keeps the `typecheck` job green —
      the non-blocking design working exactly as intended, verified against the real platform, not
      just asserted.
- [x] Updated `README.md`/`README.pt-BR.md`'s CI/CD and Roadmap sections to state the real
      verification (with the PR link) instead of "not yet verified against a real GitHub Actions
      run" — the previous, now-outdated caveat.

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

### Session 5 — Observability + Cost & Performance

- [x] Added logging to `generation/answer.py` (previously zero, the last gap under F-06): `DEBUG`
      per tool call, `WARNING` when a tool returns `{"error": ...}`, `WARNING` at
      `GenerationLoopExceededError` (logged at the point of failure, visible to any caller — web
      app, `scripts/run_eval.py`, future batch scripts — not just the web layer).
- [x] Added `tests/unit/test_generation_answer.py::test_answer_question_logs_warning_when_tool_returns_error`
      and `..._logs_warning_when_loop_exceeded` — proves the logging actually fires, using `caplog`,
      not just that the code exists.
- [x] Wrote `docs/observability.md` — honest inventory of what's monitored (API/generation/ingestion/
      evaluation layers) vs. what Phase 9 originally asked for (live dashboards, retrieval-specific
      latency, LLM retry/fallback tracking) and explicitly why those weren't built (single-user,
      low-volume scale doesn't justify the infrastructure yet).
- [x] Wrote `docs/cost-performance.md` — real per-request cost (~US$0.013, derived from actual
      measured tokens, not guessed) and a latency breakdown from the 30 real requests across the 2
      Session 2/3 eval runs. Concluded no optimization is currently justified — the data doesn't
      show a real bottleneck (context size, retrieval latency, and redundant calls were all checked
      against the real traces and ruled out).
- [x] Updated `docs/PRD.md` §13's previously-placeholder cost line ("A estimar") with the real
      measured figure and a link to `docs/cost-performance.md`.
- [x] Updated `docs/audit/TECHNICAL_AUDIT.md`: F-05 and F-06 now fully Resolved; added F-19 as a
      still-open, deliberately-not-addressed item (dashboard doesn't cover chat/generation traffic).

### Session 6 — Testing + Docker + CI/CD

- [x] Added `tests/e2e/` — real full-stack tests (FastAPI app + real Postgres, only the outbound
      Anthropic call mocked) proving the complete request path works, including a real
      `InsufficientDataError` surfacing correctly through the whole stack.
- [x] Added `tests/evaluation/README.md` documenting where evaluation logic actually lives
      (preserving existing organization rather than physically moving working test files).
- [x] **Fixed F-12** (migrations not idempotent): added a `schema_migrations` tracking table to
      `scripts/apply_migrations.py`. Verified 3 ways — bootstrapped on the real dev DB (no data
      touched), fresh-applied against a throwaway container, re-run confirmed as a clean no-op.
- [x] **Fixed F-07** (app not containerized): wrote `Dockerfile` (multi-stage, non-root, healthcheck)
      and added an `app` service to `docker-compose.yml`. Built and brought up the full stack for
      real, confirmed both containers healthy, confirmed the app container reaches Postgres over the
      Docker network and sees the real 2,644-row dataset. Published only to `127.0.0.1` on the host
      to preserve the no-auth/localhost-only security posture even when containerized.
- [x] Found and fixed a real gap while validating CI design: `tests/integration/*` (and the new
      `tests/e2e/`) assert against real historical data and were never designed to pass against a
      freshly-migrated empty Postgres — meaning CI as first designed would have failed. Fixed by
      creating `db/seed/dev_seed.sql` (a real, public-data snapshot of `ingestion_job_run`,
      `ibov_daily_history`, `cvm_feed_item`) and verifying the full integration+e2e+security suite
      (39 tests) passes against a genuinely fresh, seeded Postgres — not just the pre-existing dev DB.
- [x] Measured a real mypy baseline (18 errors, 7 files) before deciding whether/how to add type
      checking — added `mypy` as a dev dependency, configured non-blocking in CI, documented the
      baseline explicitly rather than suppressing it or silently omitting type-checking altogether.
- [x] **Fixed F-01** (no CI/CD): `.github/workflows/ci.yml` (lint, mypy, unit, integration, security
      + `pip-audit`, Docker build) and `.github/workflows/eval.yml` (real eval + regression gate,
      deliberately manual/scheduled-only given real API cost, not per-PR). Both validated by running
      the equivalent commands locally against fresh containers/DBs (see Test/validation runs below)
      — **not yet verified against an actual GitHub Actions run**, since that requires pushing to a
      GitHub remote, which wasn't done this session.
- [x] Updated `docs/architecture/deployment.md` to reflect the new containerized/idempotent/CI'd
      reality, and `docs/audit/TECHNICAL_AUDIT.md`'s status table (F-01, F-07, F-09, F-12, F-18 all
      updated).

### Session 7 — Deployment + System Design + ADRs

- [x] Wrote `docs/deployment/strategy.md` — compared 5 real deployment options (stay local,
      Tailscale, cheap VPS, PaaS, serverless) against this system's actual constraints, including
      explicitly weighing the fact that this project already hit one free-tier resource-limit wall
      (the original Supabase migration). Chose Tailscale-first with a documented VPS upgrade path,
      rather than picking a cloud provider arbitrarily.
- [x] Wrote all 8 ADRs (`docs/adr/ADR-001` through `ADR-008`): LLM selection, RAG architecture,
      retrieval strategy, evaluation strategy, tool calling, observability, security, deployment —
      each with Context/Decision/Alternatives/Trade-offs/Consequences, consolidating decisions
      already made and evidenced across Sessions 1-6 rather than introducing new unreviewed choices.
- [x] Wrote `docs/system-design/` (context, architecture, scalability, reliability, security,
      trade-offs) — the interview-support layer, with a concrete "what would need to change to
      scale this" analysis (connection pooling, caching, rate limiting, in that order) rather than a
      vague "it would need work."
- [x] Updated `docs/architecture/deployment.md`'s cross-references and confirmed consistency with
      the new `docs/deployment/strategy.md`.

### Session 8 — README + Portfolio Case + Final Validation

- [x] Asked the user's language preference for the README (bilingual chosen) rather than assuming —
      a real audience/positioning decision, not a technical correctness question.
- [x] Rewrote `README.md` (English) and added `README.pt-BR.md` (Portuguese) — full 20-section
      technical landing page per the original brief's structure, fixing both stale claims the
      Session 1 audit found and correcting the "RAG" framing per ADR-002. Real, current numbers used
      throughout (166 tests, real evaluation scores, real cost figures) — verified via
      `pytest --collect-only` immediately before writing, not recalled from memory.
- [x] Wrote `docs/portfolio/` (portfolio-summary.md, technical-highlights.md, interview-guide.md) —
      used "production-oriented" rather than "production-ready" per the brief's own instruction,
      since production-readiness genuinely isn't provable here (no real deployment, no auth).
- [x] Wrote `CHANGELOG.md` covering all 8 sessions.
- [x] Wrote `docs/audit/FINAL_ENGINEERING_REPORT.md` — before/after, architecture, testing,
      evaluation, security, observability, CI/CD, deployment, remaining gaps, portfolio value.
- [x] Final validation pass: lint (clean), `ruff format --check` (found 21 pre-existing files never
      part of this session's work — reformatted only the 3 files this session actually authored/
      touched, left the rest alone per the preservation rule — see `docs/audit/TECHNICAL_AUDIT.md`
      new finding), mypy (18-error baseline unchanged, as expected), full unit suite (112 passed),
      full integration/e2e/security suite (39 passed), the regression check against already-persisted
      results (PASSOU, no new API cost), a fresh Docker build (succeeded), and `docker compose config`
      validation. Did **not** re-run `docker compose up` end-to-end a third time — Session 6 already
      verified that fully (build → up → both healthy → real data over the network) and nothing in
      `docker-compose.yml`/`Dockerfile` changed since; re-doing it would have required disrupting the
      currently-running local dev Postgres for no new information.
- [x] Did **not** push to the GitHub remote or verify `ci.yml`/`eval.yml` against a real GitHub
      Actions run — pushing is a shared-state action requiring the user's explicit go-ahead, which
      wasn't sought mid-session; flagged as the one explicitly unverified piece in the final report
      rather than silently left unmentioned.

## In progress

- None. **All 8 sessions of the flagship-project transformation are complete.**

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
- Session 6: chose to measure the real mypy baseline (18 errors) before deciding how to add type
  checking, then added it to CI as non-blocking with the baseline documented, rather than either (a)
  skipping type-checking entirely or (b) spending this session's budget fixing 18 pre-existing type
  errors in working, tested, audited code with no concrete bug driving the fix.
- Session 6: discovered mid-implementation that the existing integration test suite (predates this
  session) was never designed to run against a fresh/empty Postgres — it asserts real historical
  values. Rather than leave the new CI workflow silently broken (or claim it works without checking),
  built and verified a real-data seed fixture (`db/seed/dev_seed.sql`) and proved the full suite
  passes against a genuinely fresh, seeded database before considering CI done.
- Session 6: `docker-compose.yml`'s `app` service publishes only to `127.0.0.1:8000` on the host
  (not `0.0.0.0`), a deliberate choice to keep the no-auth security posture unchanged by
  containerization — noted explicitly in both the compose file and `docs/architecture/deployment.md`
  rather than left as an implicit side-effect.

## Next steps — post-project (nothing left in the planned 8-session sequence)

The planned sequence, plus the post-project push/CI verification follow-up, are both complete. What
remains is entirely optional follow-up, not blocking the project's current state:

1. ~~Push to GitHub and verify `ci.yml`/`eval.yml` against a real GitHub Actions run~~ — **done**:
   [PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1), `ci.yml` verified passing
   twice for real (including a real bug found and fixed on the first run). `eval.yml` itself has
   not been triggered — it's manual/scheduled by design and needs a real `ANTHROPIC_API_KEY` GitHub
   secret configured first, which wasn't set up this session.
2. Add Anthropic API credit to unblock: re-verifying the 15 `llm_eval` tests fresh, running the
   3rd+ evaluation calibration run to properly firm up the regression baseline (currently n=2), any
   new adversarial/prompt-injection testing against the live model, and (new) configuring the
   `ANTHROPIC_API_KEY` repository secret so `eval.yml` can actually run in GitHub Actions.
3. Decide whether to merge PR #1 into `main` — left open deliberately, a merge decision belongs to
   the project owner, not something to do unprompted.
4. If a live/public demo becomes a real priority for portfolio purposes, `docs/deployment/strategy.md`
   Option C (a cheap VPS) is the documented, ready-to-execute path — auth and rate limiting would
   need to be built first per that document.
5. Optional, non-blocking cleanup: the 18-error mypy baseline, the 21 pre-existing files not
   `ruff format`-clean (see the note added to `docs/audit/TECHNICAL_AUDIT.md` this session), and a
   frozen-snapshot fixture for retrieval-quality metrics if that ever becomes a priority.

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
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 5, after observability logging changes) | 112 passed, 52 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 5) | All checks passed |
| 2026-08-27 | `.venv/bin/python scripts/apply_migrations.py` (Session 6, fresh throwaway Postgres) | 11 applied |
| 2026-08-27 | `.venv/bin/python scripts/apply_migrations.py` (Session 6, re-run same container) | 0 applied, 11 skipped — idempotency confirmed |
| 2026-08-27 | `docker build -t rag-b3-app:test .` (Session 6) | Build succeeded |
| 2026-08-27 | `docker compose up -d` (Session 6, full stack) | Both containers healthy; app→postgres connectivity confirmed with real data (2,644 rows) visible over the Docker network |
| 2026-08-27 | `.venv/bin/python -m pytest -q -m integration tests/integration/ tests/e2e/ tests/security/` (Session 6, against fresh Postgres + `db/seed/dev_seed.sql`) | 39 passed |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 6, final) | 112 passed, 54 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 6) | All checks passed |
| 2026-08-27 | `.venv/bin/python -m mypy src --ignore-missing-imports` (Session 6, baseline measurement) | 18 errors, 7 files — documented, not fixed this session |
| 2026-08-27 | `.venv/bin/python -c "import yaml; ..."` (Session 6, workflow YAML syntax check) | Both `ci.yml`/`eval.yml` valid YAML |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 7, sanity check — docs-only session) | 112 passed, 54 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 8, final validation) | All checks passed |
| 2026-08-27 | `.venv/bin/python -m ruff format --check src tests scripts` (Session 8) | 21 pre-existing files flagged (not this session's work — see note); the 3 files this session authored/touched were reformatted and re-verified clean |
| 2026-08-27 | `.venv/bin/python -m mypy src --ignore-missing-imports` (Session 8, final) | 18 errors, 7 files — unchanged baseline, as expected |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 8, final) | 112 passed, 54 deselected |
| 2026-08-27 | `.venv/bin/python -m pytest -q -m integration` (Session 8, final) | 39 passed |
| 2026-08-27 | `.venv/bin/python scripts/check_regression.py` (Session 8, no new API cost) | REGRESSION CHECK: PASSOU |
| 2026-08-27 | `docker build -t rag-b3-app:final-check .` (Session 8, final) | Build succeeded |
| 2026-08-27 | `docker compose config -q` (Session 8, final) | Valid |
| 2026-08-27 | `docker compose up -d --build` (post-project, full stack, alt port) | Both services healthy |
| 2026-08-27 | `POST /api/ask` against the real running container (post-project) | HTTP 500, generic message only — real Anthropic billing error logged server-side, confirmed not leaked to client |
| 2026-08-27 | `git push origin chore/finalize-and-migrate-postgres` (post-project) | 24 commits pushed |
| 2026-08-27 | `gh pr create` (post-project) | [PR #1](https://github.com/marcotuliorod/RAG_Finance_IBOV/pull/1) created |
| 2026-08-27 | GitHub Actions `ci.yml` run #33093690129 (post-project, real platform run) | 6/6 jobs passed; annotations revealed the `setup-uv` `python-version` bug |
| 2026-08-27 | GitHub Actions `ci.yml` run #33093844986 (post-project, after the fix) | 6/6 jobs passed, `python-version` warning gone, mypy non-blocking behavior confirmed working as designed |
