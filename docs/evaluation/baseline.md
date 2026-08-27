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

## Run record

- **Run timestamp:** 2026-08-27T14:43:06Z
- **Raw artifact:** [`results/2026-08-27T144306_489140+0000.json`](results/2026-08-27T144306_489140+0000.json)
- **Generator model:** `claude-sonnet-5` (as configured in `.env` / `config/settings.py` default — live-confirmed, see `methodology.md`)
- **Judge model:** `claude-opus-4-8` (live-confirmed)
- **Golden dataset:** `golden_v1.json`, version 1.0, 15 cases
- **Database state:** local Postgres, `ibov_daily_history` 2,644 rows (2016-01-04 → 2026-08-24), `cvm_feed_item` 60 rows

## Results

| Metric | Value | Threshold | Result |
|---|---|---|---|
| Mean faithfulness | **0.909** | ≥ 0.85 | PASS |
| Mean answer relevancy | **0.973** | ≥ 0.80 | PASS |
| Error rate | **0.0%** (0/15) | — | — |
| Mean generation latency | 7.25s / request | — | — |
| Total generation tokens | 77,301 in / 6,371 out | — | — |
| Total judge tokens | 40,317 in / 12,971 out | — | — |
| Estimated total cost (15 cases, gen + judge) | **US$ 0.74** | — | — |
| **Gate** | | | **PASSED** |

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

This is a single run, not a distribution — no variance/confidence interval
is computed across repeated runs (the LLM judge is not deterministic
run-to-run). Session 3's regression-testing work is expected to define a
tolerance band around this number (not a single-run cliff-edge threshold)
before wiring a CI gate on top of it — see
`docs/audit/IMPLEMENTATION_PROGRESS.md` for that session's scope. This
document intentionally stops at "here is what was measured," not "here is
the pass/fail band for future runs."
