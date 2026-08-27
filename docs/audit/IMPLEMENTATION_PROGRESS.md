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

**Session 2 — RAG Pipeline + Evaluation.** Status: complete.

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

## In progress

- None. Session 2 scope is closed.

## Blocked

- None.

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

## Next steps (Session 3 — Regression + Golden Dataset)

1. Define a regression tolerance band around the 0.909/0.973 baseline (not a single-run cliff-edge)
   — `docs/evaluation/regression.md`.
2. Wire a regression check that can run in CI once Session 6 adds CI (the check logic itself can be
   built now; the pipeline wiring happens later — don't block on CI existing first).
3. Write `docs/evaluation/model-regression-case-study.md` — the Sonnet→Haiku→Sonnet case study,
   now with a real, artifact-backed post-revert baseline to anchor it (previously only had the
   pre-Haiku prose number to point to).
4. Consider whether golden dataset v1's unused `last_passed` field (present in every case, never
   read by any code — confirmed via repo-wide grep) should be wired up or removed; not fixed this
   session to avoid scope creep into Session 3's actual focus.
5. Review whether the 2 retrieval-dependent golden cases would benefit from a frozen CVM snapshot
   fixture (see `docs/evaluation/methodology.md` limitation note) if retrieval metrics become a
   priority.

## Test/validation runs performed

| Date | Command | Result |
|---|---|---|
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 1, audit agent, read-only) | 88 passed, 42 deselected |
| 2026-08-27 | `.venv/bin/python -m pytest --collect-only -q -m ""` (Session 1, audit agent) | 130 collected |
| 2026-08-27 | `.venv/bin/python -m pytest -q` (Session 2, after engineering-metrics changes) | 92 passed, 42 deselected |
| 2026-08-27 | `.venv/bin/python -m ruff check src tests scripts` (Session 2) | All checks passed |
| 2026-08-27 | `.venv/bin/python -m pytest -q -m integration` (Session 2, real Postgres) | 27 passed |
| 2026-08-27 | `.venv/bin/python scripts/run_eval.py` (Session 2, real API — real cost ~US$0.74) | faithfulness 0.909, relevancy 0.973, 0% errors, GATE: PASSOU |
