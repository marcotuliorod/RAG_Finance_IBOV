# ADR-004: Evaluation Strategy

## Status

Accepted, extended Session 2/3 (real baseline persistence, regression
check).

## Context

The system needs a way to measure generation quality (faithfulness,
relevancy) and catch regressions from prompt/model changes — the exact
category of problem the Sonnet→Haiku→Sonnet incident demonstrated is real
(`docs/evaluation/model-regression-case-study.md`).

## Decision

- **Golden dataset**: 15 hand-authored cases
  (`data/datasets/eval/golden_v1.json`) spanning factual, temporal,
  aggregation, multi-hop, and 4 adversarial categories, with deterministic
  `resolver` functions for 10/15 cases (verifiable with no LLM at all).
- **Custom LLM-as-judge**, not `ragas` — `ragas==0.4.3`'s import chain was
  broken in the available environment (`docs/evaluation/methodology.md`);
  the same technique (claim decomposition + context-support checking) is
  reimplemented directly against the Anthropic SDK with forced tool-use for
  structured output (`src/rag_b3/eval/judge.py`).
- **Two-tier regression gate**: an absolute floor (faithfulness ≥ 0.85,
  relevancy ≥ 0.80 — pre-existing project threshold) plus a relative check
  against a measured baseline (`src/rag_b3/eval/regression.py`,
  `docs/evaluation/regression.md`), added Session 3.
- **Every run persisted** as a timestamped JSON artifact
  (`docs/evaluation/results/`) — added Session 2, since no prior run had
  ever been saved (only hand-typed prose summaries existed before).

## Alternatives considered

| Option | Why not chosen |
|---|---|
| `ragas` (reconsider later) | Broken import in the available version; revisit if a future release fixes it — noted directly in `judge.py`'s docstring, not dismissed permanently. |
| A single absolute threshold only (no relative baseline check) | Wouldn't catch a regression that stays above the absolute floor but is still a real quality drop (e.g. 0.92 → 0.87) — the two-tier design specifically closes this gap, proven via `tests/unit/test_eval_regression.py`. |
| A larger golden dataset (50+ cases) | Not built — 15 well-chosen cases (including all 4 required adversarial categories) already surfaced a real regression once; expanding the dataset is reasonable future work but wasn't necessary to demonstrate the methodology works, and each case adds real API cost per eval run. |
| Automatic per-commit evaluation in CI | Rejected given real cost (~US$0.74/run) — `.github/workflows/eval.yml` is manual/scheduled instead (see ADR-008 and `docs/evaluation/regression.md` for the full cost trade-off). |

## Trade-offs

The regression tolerance (`docs/evaluation/baseline.json`) is calibrated
from only 2 real runs (a 3rd was blocked by an API billing limit) — an
explicitly acknowledged statistical weakness, not hidden. The tolerance was
set conservatively (well above the measured 2-run stdev, well below the
actual historical regression's magnitude) specifically to be safe under
that uncertainty rather than either too tight (false alarms) or too loose
(misses real regressions).

## Consequences

- Any future model, prompt, or tool change should run
  `scripts/run_eval.py` + `scripts/check_regression.py` before being
  adopted — this is now a real, executable step, not an aspiration.
- The baseline should be recalibrated with ≥5 runs once API budget allows
  (`docs/evaluation/regression.md`) — tracked as explicit follow-up, not
  silently left as a permanent n=2 baseline.
- Retrieval-quality metrics (Precision@K/Recall@K/MRR) remain unmeasured —
  a stated, reasoned limitation (ADR-003), not an oversight.
