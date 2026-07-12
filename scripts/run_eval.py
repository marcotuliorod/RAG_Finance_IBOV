#!/usr/bin/env python3
"""Avaliação de qualidade da camada de geração (faithfulness + answer
relevancy) sobre o golden dataset — gate descrito em constitution.md/
validation.md (faithfulness ≥ 0.85, answer relevancy ≥ 0.80).

Roda os 15 casos reais contra o Claude (gerador: claude-sonnet-5) e depois
julga cada resposta com um segundo modelo (claude-opus-4-8, ver
rag_b3.eval.judge) para evitar identity bias. Não usa o pacote `ragas`
(import quebrado na versão disponível — ver judge.py) mas segue a mesma
técnica de LLM-as-judge."""

import json
import logging
import sys
from pathlib import Path

import anthropic

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings
from rag_b3.eval.judge import score_answer_relevancy, score_faithfulness
from rag_b3.generation.answer import answer_question

logger = logging.getLogger(__name__)

GOLDEN_PATH = Path(__file__).parent.parent / "data" / "datasets" / "eval" / "golden_v1.json"
FAITHFULNESS_THRESHOLD = 0.85
RELEVANCY_THRESHOLD = 0.80


def main() -> int:
    configure_logging()
    settings = get_settings()
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]

    gen_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    judge_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    faithfulness_scores = []
    relevancy_scores = []

    with get_connection(settings.supabase_db_url) as conn:
        for case in cases:
            result = answer_question(conn, case["query"], client=gen_client)
            contexts = [json.dumps(tc["result"], ensure_ascii=False) for tc in result.tool_calls]

            faithfulness = score_faithfulness(judge_client, case["query"], result.text, contexts)
            relevancy = score_answer_relevancy(judge_client, case["query"], result.text)

            faithfulness_scores.append(faithfulness.score)
            relevancy_scores.append(relevancy.score)

            print("=" * 100)
            print(f"[{case['id']}] {case['query']}")
            print(f"faithfulness: {faithfulness.score:.2f}  ({len(faithfulness.claims)} claims)")
            for claim in faithfulness.claims:
                if not claim.supported:
                    print(f"  NÃO SUSTENTADO: {claim.claim} — {claim.reasoning}")
            print(f"relevancy   : {relevancy.score:.2f}  — {relevancy.reasoning}")

    mean_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
    mean_relevancy = sum(relevancy_scores) / len(relevancy_scores)

    print("=" * 100)
    print(f"Faithfulness média : {mean_faithfulness:.3f} (threshold {FAITHFULNESS_THRESHOLD})")
    print(f"Relevancy média    : {mean_relevancy:.3f} (threshold {RELEVANCY_THRESHOLD})")

    passed = mean_faithfulness >= FAITHFULNESS_THRESHOLD and mean_relevancy >= RELEVANCY_THRESHOLD
    print("GATE: PASSOU" if passed else "GATE: FALHOU")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
