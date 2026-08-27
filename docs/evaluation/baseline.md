# Evaluation Baseline

**This is the first baseline recorded as a persisted artifact.** All earlier
figures referenced in `.specify/memory/constitution.md`,
`.specify/specs/001-.../validation.md`, and `docs/PRD.md` (faithfulness
0.899/0.767, relevancy 0.973/0.963) exist only as hand-typed prose — no raw
run output backed them (see `docs/audit/TECHNICAL_AUDIT.md` §4/§6.2). This
document reports the first run made with `scripts/run_eval.py` after it was
extended (this session) to persist results, and it is the number those
earlier docs recommended re-confirming after the Haiku→Sonnet revert on
2026-08-24.

## Run records

Two runs were made this session to get a real (if thin, n=2) measure of
run-to-run variance for `docs/evaluation/regression.md`'s tolerance
calibration. A third was attempted and blocked by an Anthropic API billing
limit — reported honestly rather than omitted; see `regression.md` §"Known
limitation".

| | Run 1 | Run 2 |
|---|---|---|
| Timestamp | 2026-08-27T14:43:06Z | 2026-08-27T14:53:46Z |
| Raw artifact | [`results/2026-08-27T144306_489140+0000.json`](results/2026-08-27T144306_489140+0000.json) | [`results/2026-08-27T145346_606757+0000.json`](results/2026-08-27T145346_606757+0000.json) |
| Faithfulness | 0.909 | 0.935 |
| Relevancy | 0.973 | 0.977 |
| Error rate | 0.0% | 0.0% |
| Est. cost | US$ 0.74 | US$ 0.74 |

- **Generator model:** `claude-sonnet-5` (as configured in `.env` / `config/settings.py` default — live-confirmed, see `methodology.md`)
- **Judge model:** `claude-opus-4-8` (live-confirmed)
- **Golden dataset:** `golden_v1.json`, version 1.0, 15 cases
- **Database state:** local Postgres, `ibov_daily_history` 2,644 rows (2016-01-04 → 2026-08-24), `cvm_feed_item` 60 rows

## Calibrated baseline (mean of the 2 runs)

Recorded in [`baseline.json`](baseline.json) — machine-readable, consumed by
`scripts/check_regression.py`.

| Metric | Mean | Stdev (n=2) | Threshold | Result |
|---|---|---|---|---|
| Faithfulness | **0.922** | 0.018 | ≥ 0.85 | PASS |
| Answer relevancy | **0.975** | 0.003 | ≥ 0.80 | PASS |
| Error rate | **0.0%** | — | — | — |
| **Gate** | | | | **PASSED** (both runs) |

## Comparison to the previously-documented (unpersisted) figures

| | Sonnet (original, pre-Haiku, prose-only) | Haiku (regression, prose-only) | Sonnet (this run, persisted) |
|---|---|---|---|
| Faithfulness | 0.899 | 0.767 | **0.909** |
| Relevancy | 0.973 | 0.963 | **0.973** |
| Source | narrative in `constitution.md`/`validation.md` | same | this run's JSON artifact |

The reconfirmed number (0.909) is consistent with — in fact marginally
higher than — the originally reported 0.899, and closes the specific gap
flagged in `docs/audit/TECHNICAL_AUDIT.md` F-04: the post-revert baseline is
no longer an unverified carry-over number, it is a measured, artifact-backed
result. The small difference (0.899 vs. 0.909) is within the kind of
run-to-run variance expected from an LLM judge scoring free-text generation
and is not being treated as a meaningful change — see the "recurring
faithfulness deduction" note in `methodology.md` for the dominant, systematic
source of the sub-1.0 scores in both runs (a disclosure sentence the judge
correctly can't ground in tool-call context).

## Per-case detail

All 15 cases passed with no errors. Two categories are worth calling out
explicitly:

- **Adversarial cases (012, 013, 014, 015)** — out-of-domain (individual
  stock quote), out-of-scope (investment recommendation), insufficient-data
  (1990, before the series starts), and forecast-refusal — all four scored
  faithfulness 1.00 (zero or near-zero factual claims, since a correct
  refusal makes no assertions to fact-check) and relevancy 0.90–1.00
  (refusals were clearly communicated, which the judge instructions treat
  as highly relevant). This is a genuine, positive signal for the system's
  core grounding/refusal design, not just a vacuous pass.
- **Retrieval-dependent cases (010, 011)** — faithfulness 1.00/1.00,
  relevancy 0.90/0.90. Case 011 (multi-hop: latest CVM sanction → next
  trading day's index move) correctly identified that the relevant sanction
  predates the Ibovespa series (2014 vs. series start 2016-07-11) and
  reported insufficient data rather than guessing — the intended behavior
  for a multi-hop case that hits a hard data boundary.

Full per-case claims, reasoning text, and engineering metrics are in the raw
JSON artifact linked above.

## What this baseline is (and isn't) good for

n=2 is enough to build and unit-test a working regression check (see
`docs/evaluation/regression.md`), and enough to prove — with the actual
historical Haiku numbers fed through the real check logic — that it would
have caught the known regression with wide margin. It is **not** enough for
a statistically confident tolerance band; `baseline.json` says so explicitly
and recommends recalibrating with ≥5 runs once more API budget is
available. This document intentionally reports what was measured rather
than overstating the confidence behind it.
