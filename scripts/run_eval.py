#!/usr/bin/env python3
"""Avaliação de qualidade da camada de geração (faithfulness + answer
relevancy) sobre o golden dataset — gate descrito em constitution.md/
validation.md (faithfulness ≥ 0.85, answer relevancy ≥ 0.80).

Roda os 15 casos reais contra o Claude (gerador: configurado via
ANTHROPIC_MODEL, default claude-sonnet-5) e depois julga cada resposta com
um segundo modelo (claude-opus-4-8, ver rag_b3.eval.judge) para evitar
identity bias. Não usa o pacote `ragas` (import quebrado na versão
disponível — ver judge.py) mas segue a mesma técnica de LLM-as-judge.

Além das métricas de qualidade, captura métricas de engenharia por caso —
tokens de entrada/saída, latência, custo estimado (rag_b3.common.pricing) e
taxa de erro — e persiste tudo em docs/evaluation/results/<timestamp>.json,
para permitir comparação histórica/regressão (nenhum resultado de eval era
persistido antes desta mudança — ver docs/audit/TECHNICAL_AUDIT.md F-03)."""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import anthropic

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.common.pricing import estimate_cost_usd
from rag_b3.config.settings import get_settings
from rag_b3.eval.judge import JUDGE_MODEL, score_answer_relevancy, score_faithfulness
from rag_b3.generation.answer import GenerationLoopExceededError, answer_question

logger = logging.getLogger(__name__)

GOLDEN_PATH = Path(__file__).parent.parent / "data" / "datasets" / "eval" / "golden_v1.json"
RESULTS_DIR = Path(__file__).parent.parent / "docs" / "evaluation" / "results"
FAITHFULNESS_THRESHOLD = 0.85
RELEVANCY_THRESHOLD = 0.80


def main() -> int:
    configure_logging()
    settings = get_settings()
    dataset = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = dataset["cases"]

    gen_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    judge_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    case_results = []
    errors = 0

    with get_connection(settings.database_url) as conn:
        for case in cases:
            try:
                gen = answer_question(conn, case["query"], client=gen_client)
            except GenerationLoopExceededError as exc:
                errors += 1
                print("=" * 100)
                print(f"[{case['id']}] {case['query']}")
                print(f"ERRO: {exc}")
                case_results.append(
                    {
                        "id": case["id"],
                        "query": case["query"],
                        "category": case.get("category"),
                        "difficulty": case.get("difficulty"),
                        "error": str(exc),
                    }
                )
                continue

            contexts = [json.dumps(tc["result"], ensure_ascii=False) for tc in gen.tool_calls]

            faithfulness = score_faithfulness(judge_client, case["query"], gen.text, contexts)
            relevancy = score_answer_relevancy(judge_client, case["query"], gen.text)

            judge_input_tokens = faithfulness.input_tokens + relevancy.input_tokens
            judge_output_tokens = faithfulness.output_tokens + relevancy.output_tokens
            gen_cost = estimate_cost_usd(gen.model_id, gen.input_tokens, gen.output_tokens)
            judge_cost = estimate_cost_usd(JUDGE_MODEL, judge_input_tokens, judge_output_tokens)

            print("=" * 100)
            print(f"[{case['id']}] {case['query']}")
            print(f"faithfulness: {faithfulness.score:.2f}  ({len(faithfulness.claims)} claims)")
            for claim in faithfulness.claims:
                if not claim.supported:
                    print(f"  NÃO SUSTENTADO: {claim.claim} — {claim.reasoning}")
            print(f"relevancy   : {relevancy.score:.2f}  — {relevancy.reasoning}")
            print(
                f"engenharia  : {gen.latency_seconds:.2f}s, "
                f"{gen.input_tokens}+{gen.output_tokens} tokens geração "
                f"({gen.api_calls} chamadas), modelo={gen.model_id}"
            )

            case_results.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "category": case.get("category"),
                    "difficulty": case.get("difficulty"),
                    "faithfulness_score": faithfulness.score,
                    "faithfulness_claims": [c.model_dump() for c in faithfulness.claims],
                    "relevancy_score": relevancy.score,
                    "relevancy_reasoning": relevancy.reasoning,
                    "generation": {
                        "model_id": gen.model_id,
                        "input_tokens": gen.input_tokens,
                        "output_tokens": gen.output_tokens,
                        "api_calls": gen.api_calls,
                        "latency_seconds": gen.latency_seconds,
                        "tool_calls": len(gen.tool_calls),
                        "estimated_cost_usd": gen_cost,
                    },
                    "judge": {
                        "model_id": JUDGE_MODEL,
                        "input_tokens": judge_input_tokens,
                        "output_tokens": judge_output_tokens,
                        "estimated_cost_usd": judge_cost,
                    },
                }
            )

    scored = [c for c in case_results if "error" not in c]
    faithfulness_scores = [c["faithfulness_score"] for c in scored]
    relevancy_scores = [c["relevancy_score"] for c in scored]

    mean_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if scored else 0.0
    mean_relevancy = sum(relevancy_scores) / len(relevancy_scores) if scored else 0.0
    error_rate = errors / len(cases)

    total_gen_input = sum(c["generation"]["input_tokens"] for c in scored)
    total_gen_output = sum(c["generation"]["output_tokens"] for c in scored)
    total_judge_input = sum(c["judge"]["input_tokens"] for c in scored)
    total_judge_output = sum(c["judge"]["output_tokens"] for c in scored)
    total_cost = sum(
        (c["generation"]["estimated_cost_usd"] or 0) + (c["judge"]["estimated_cost_usd"] or 0)
        for c in scored
    )
    mean_latency = (
        sum(c["generation"]["latency_seconds"] for c in scored) / len(scored) if scored else 0.0
    )

    print("=" * 100)
    print(f"Faithfulness média : {mean_faithfulness:.3f} (threshold {FAITHFULNESS_THRESHOLD})")
    print(f"Relevancy média    : {mean_relevancy:.3f} (threshold {RELEVANCY_THRESHOLD})")
    print(f"Taxa de erro       : {error_rate:.1%} ({errors}/{len(cases)} casos)")
    print(f"Latência média (geração): {mean_latency:.2f}s")
    print(
        f"Tokens totais      : geração {total_gen_input}+{total_gen_output}, "
        f"juiz {total_judge_input}+{total_judge_output}"
    )
    print(f"Custo estimado total: US$ {total_cost:.4f}")

    passed = (
        mean_faithfulness >= FAITHFULNESS_THRESHOLD
        and mean_relevancy >= RELEVANCY_THRESHOLD
        and errors == 0
    )
    print("GATE: PASSOU" if passed else "GATE: FALHOU")

    run_record = {
        "run_at": datetime.now(UTC).isoformat(),
        "golden_dataset_version": dataset.get("version"),
        "generator_model_configured": settings.anthropic_model,
        "judge_model": JUDGE_MODEL,
        "thresholds": {
            "faithfulness": FAITHFULNESS_THRESHOLD,
            "relevancy": RELEVANCY_THRESHOLD,
        },
        "aggregate": {
            "mean_faithfulness": mean_faithfulness,
            "mean_relevancy": mean_relevancy,
            "error_rate": error_rate,
            "errors": errors,
            "total_cases": len(cases),
            "mean_generation_latency_seconds": mean_latency,
            "total_generation_input_tokens": total_gen_input,
            "total_generation_output_tokens": total_gen_output,
            "total_judge_input_tokens": total_judge_input,
            "total_judge_output_tokens": total_judge_output,
            "estimated_total_cost_usd": total_cost,
            "gate_passed": passed,
        },
        "cases": case_results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{run_record['run_at'].replace(':', '').replace('.', '_')}.json"
    out_path.write_text(json.dumps(run_record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Resultado salvo em: {out_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
