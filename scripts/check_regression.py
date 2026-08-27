#!/usr/bin/env python3
"""Compara o resultado de avaliação mais recente (docs/evaluation/results/)
contra o baseline calibrado (docs/evaluation/baseline.json) e falha
(exit 1) se houver regressão — nem sempre igual ao gate absoluto de
scripts/run_eval.py (faithfulness >= 0.85, relevancy >= 0.80): a lógica em
rag_b3.eval.regression soma um segundo critério, relativo ao baseline
medido, para pegar uma queda que ainda passe no piso absoluto mas já
represente uma regressão real (ex.: baseline 0.92 -> novo run 0.87 passa no
piso 0.85 mas é uma queda de qualidade real que este check detecta).

Não roda geração/avaliação — espera que `scripts/run_eval.py` já tenha
rodado e salvo um resultado em docs/evaluation/results/. Pensado para virar
o passo de CI descrito em docs/evaluation/regression.md (ainda sem CI real
neste repositório — ver docs/audit/TECHNICAL_AUDIT.md F-01)."""

import json
import sys
from pathlib import Path

from rag_b3.eval.regression import check_run_against_baseline

RESULTS_DIR = Path(__file__).parent.parent / "docs" / "evaluation" / "results"
BASELINE_PATH = Path(__file__).parent.parent / "docs" / "evaluation" / "baseline.json"


def _latest_result_path() -> Path:
    results = sorted(RESULTS_DIR.glob("*.json"))
    if not results:
        raise SystemExit(f"Nenhum resultado em {RESULTS_DIR} — rode scripts/run_eval.py primeiro.")
    return results[-1]


def main() -> int:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    latest_path = _latest_result_path()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))

    print(
        f"Baseline    : {BASELINE_PATH.name} "
        f"(n={baseline['faithfulness']['n']}, calibrado em {baseline['established_at']})"
    )
    print(f"Run avaliado: {latest_path.name} ({latest['run_at']})")
    print("-" * 100)

    checks = check_run_against_baseline(latest["aggregate"], baseline)
    for check in checks:
        status = "OK" if check.passed else "REGRESSÃO"
        print(
            f"{check.name:12s}: observado={check.observed:.3f}  "
            f"baseline={check.baseline_mean:.3f}  piso_absoluto={check.hard_floor:.3f}  "
            f"limite_efetivo={check.effective_threshold:.3f}  [{status}]"
        )

    passed = all(c.passed for c in checks)
    print("-" * 100)
    print("REGRESSION CHECK: PASSOU" if passed else "REGRESSION CHECK: FALHOU")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
