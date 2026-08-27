# Evaluation tests

The project's roadmap calls for a `tests/evaluation/` directory. This file
exists to explain where that logic actually lives rather than duplicating
it here — the project's preservation rule favors not moving working,
already-organized code just to match a directory name.

| What | Where it actually lives |
|---|---|
| Golden dataset | `data/datasets/eval/golden_v1.json` |
| Deterministic (no-LLM) verification against the golden dataset | `tests/integration/test_golden_dataset.py` (marker `integration`) |
| Full generation + LLM-judge verification against the golden dataset | `tests/integration/test_golden_dataset_generation.py` (marker `llm_eval` — costs real API tokens, not run by default) |
| Faithfulness / answer-relevancy judge implementation | `src/rag_b3/eval/judge.py`, unit-tested in `tests/unit/test_eval_judge.py` |
| Regression-check logic (baseline comparison) | `src/rag_b3/eval/regression.py`, unit-tested in `tests/unit/test_eval_regression.py` |
| Full evaluation run + persistence | `scripts/run_eval.py` (not a pytest test — a standalone script, since it costs real money per run and shouldn't run in a normal `pytest` invocation) |
| Regression gate | `scripts/check_regression.py` |
| Methodology, baseline, regression, model-regression case study | `docs/evaluation/` |

If this ever gets consolidated into an actual `tests/evaluation/` package,
that's a real refactor (moving `test_golden_dataset*.py` and updating
`pytest.ini_options` markers) and should be its own change, not a
side-effect of adding this README.
