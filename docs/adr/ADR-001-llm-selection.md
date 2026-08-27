# ADR-001: LLM Selection

## Status

Accepted (2026-08-24, reaffirmed with fresh measurement 2026-08-27).

## Context

The generation layer needs one LLM for tool-calling chat responses, and a
second, independent model for LLM-as-judge evaluation
(`docs/evaluation/methodology.md` explains why a different model than the
generator is used for judging: avoiding identity bias).

A cost/latency-motivated experiment briefly swapped the generator to a
smaller model, which is the central event this ADR needs to account for —
see `docs/evaluation/model-regression-case-study.md` for the full incident.

## Decision

- **Generator: `claude-sonnet-5`** (configurable via `ANTHROPIC_MODEL`,
  `src/rag_b3/config/settings.py`).
- **Judge: `claude-opus-4-8`** (hardcoded in `src/rag_b3/eval/judge.py`,
  deliberately different from the generator).

## Alternatives considered

| Option | Outcome |
|---|---|
| `claude-haiku-4-5-20251001` as generator (tried 2026-07/08) | Faithfulness dropped from 0.899 to 0.767 — below the 0.85 gate. Root cause: Haiku sometimes skipped the required tool call and answered from parametric memory, breaking the system's core grounding contract. Reverted. |
| Same model for generator and judge | Rejected — risks identity bias (a model rating its own output more favorably), a known LLM-as-judge failure mode. |
| A third-party/cheaper model via a different provider | Not evaluated — would require re-implementing tool-use/structured-output integration against a different SDK for a system that was built API-first around the Anthropic SDK specifically for its tool-use ergonomics (`docs/ai/tool-calling.md`). |

## Trade-offs

Sonnet costs more per token than Haiku ($2.00/$10.00 vs. $1.00/$5.00 per 1M
tokens — `src/rag_b3/common/pricing.py`), but the real measured per-request
cost difference is negligible at this system's volume (~US$0.013/request
with Sonnet, per `docs/cost-performance.md`) — the cost savings Haiku would
have offered were never large enough in absolute terms to justify a
faithfulness regression on a system whose entire value proposition is
"trustworthy grounded answers about a financial index."

## Consequences

- Faithfulness/relevancy are now real, measured, artifact-backed numbers
  (0.909-0.935 faithfulness, 0.973-0.977 relevancy across 2 real runs —
  `docs/evaluation/baseline.md`), not the stale pre-revert figures the
  project's docs cited before Session 2/3.
- A regression check now exists (`src/rag_b3/eval/regression.py`,
  `docs/evaluation/regression.md`) that would catch a repeat of this exact
  incident automatically, once wired into CI on a schedule
  (`.github/workflows/eval.yml`) — it wasn't automatic when the Haiku
  regression actually happened; a human had to remember to re-check.
- Any future model swap (including to a newer Claude model) must go through
  `scripts/run_eval.py` + `scripts/check_regression.py` before being
  adopted — this ADR's decision is conditional on that process being
  followed, not a permanent pin to `claude-sonnet-5` specifically.
