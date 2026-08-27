"""Lógica de comparação de um resultado de avaliação contra o baseline
calibrado (docs/evaluation/baseline.json) — ver docs/evaluation/regression.md
para a metodologia completa de como o baseline/tolerância foram definidos."""

from dataclasses import dataclass


@dataclass
class MetricCheck:
    name: str
    observed: float
    baseline_mean: float
    hard_floor: float
    effective_threshold: float
    passed: bool


def check_metric(name: str, observed: float, baseline_mean: float, tolerance: float, hard_floor: float) -> MetricCheck:
    """Regride se `observed` cair abaixo do maior entre o piso absoluto
    pré-existente do projeto (hard_floor) e (baseline_mean - tolerance).
    Isso pega tanto uma queda abaixo do gate histórico quanto uma queda
    real de qualidade que ainda passaria no gate absoluto mas já
    representa uma regressão frente ao que foi medido como baseline."""
    threshold = max(hard_floor, baseline_mean - tolerance)
    return MetricCheck(
        name=name,
        observed=observed,
        baseline_mean=baseline_mean,
        hard_floor=hard_floor,
        effective_threshold=threshold,
        passed=observed >= threshold,
    )


def check_run_against_baseline(aggregate: dict, baseline: dict) -> list[MetricCheck]:
    checks = [
        check_metric(
            "faithfulness",
            aggregate["mean_faithfulness"],
            baseline["faithfulness"]["mean"],
            baseline["tolerance"]["faithfulness"],
            baseline["hard_floor"]["faithfulness"],
        ),
        check_metric(
            "relevancy",
            aggregate["mean_relevancy"],
            baseline["relevancy"]["mean"],
            baseline["tolerance"]["relevancy"],
            baseline["hard_floor"]["relevancy"],
        ),
    ]
    checks.append(
        MetricCheck(
            name="error_rate",
            observed=aggregate["error_rate"],
            baseline_mean=0.0,
            hard_floor=0.0,
            effective_threshold=0.0,
            passed=aggregate["error_rate"] == 0.0,
        )
    )
    return checks
