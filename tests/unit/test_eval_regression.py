from rag_b3.eval.regression import check_metric, check_run_against_baseline

BASELINE = {
    "faithfulness": {"mean": 0.922},
    "relevancy": {"mean": 0.975},
    "hard_floor": {"faithfulness": 0.85, "relevancy": 0.80},
    "tolerance": {"faithfulness": 0.05, "relevancy": 0.03},
}


def test_check_metric_passes_when_within_tolerance_of_baseline():
    check = check_metric(
        "faithfulness", observed=0.90, baseline_mean=0.922, tolerance=0.05, hard_floor=0.85
    )
    assert check.passed
    assert check.effective_threshold == 0.872  # 0.922 - 0.05, acima do piso 0.85


def test_check_metric_fails_when_below_tolerance_even_if_above_hard_floor():
    # 0.86 está acima do piso absoluto (0.85) mas abaixo do limite relativo
    # ao baseline (0.922 - 0.05 = 0.872) — é exatamente o cenário que o
    # gate absoluto sozinho (scripts/run_eval.py) não pegaria.
    check = check_metric(
        "faithfulness", observed=0.86, baseline_mean=0.922, tolerance=0.05, hard_floor=0.85
    )
    assert not check.passed
    assert check.effective_threshold == 0.872


def test_check_metric_fails_when_below_hard_floor_regardless_of_baseline():
    # Reproduz o cenário real da regressão Haiku: mesmo com um baseline
    # baixo (hipotético), nunca deve passar abaixo do piso histórico do
    # projeto (0.85).
    check = check_metric(
        "faithfulness", observed=0.767, baseline_mean=0.80, tolerance=0.05, hard_floor=0.85
    )
    assert not check.passed
    assert check.effective_threshold == 0.85  # piso absoluto vence, não 0.80-0.05=0.75


def test_check_run_against_baseline_catches_the_actual_haiku_regression():
    # aggregate real documentado para a troca de modelo para Haiku
    # (constitution.md/validation.md): faithfulness 0.767, relevancy 0.963.
    haiku_aggregate = {
        "mean_faithfulness": 0.767,
        "mean_relevancy": 0.963,
        "error_rate": 0.0,
    }
    checks = check_run_against_baseline(haiku_aggregate, BASELINE)
    faithfulness_check = next(c for c in checks if c.name == "faithfulness")
    assert not faithfulness_check.passed


def test_check_run_against_baseline_passes_the_actual_reconfirmed_sonnet_runs():
    for observed in (
        {"mean_faithfulness": 0.909, "mean_relevancy": 0.973, "error_rate": 0.0},
        {"mean_faithfulness": 0.935, "mean_relevancy": 0.977, "error_rate": 0.0},
    ):
        checks = check_run_against_baseline(observed, BASELINE)
        assert all(c.passed for c in checks)


def test_check_run_against_baseline_flags_nonzero_error_rate():
    aggregate = {"mean_faithfulness": 0.95, "mean_relevancy": 0.98, "error_rate": 0.1}
    checks = check_run_against_baseline(aggregate, BASELINE)
    error_check = next(c for c in checks if c.name == "error_rate")
    assert not error_check.passed
