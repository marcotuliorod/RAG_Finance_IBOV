"""Roda os 15 casos do golden dataset pela camada de geração real
(rag_b3.generation.answer.answer_question) e usa o LLM-judge
(rag_b3.eval.judge) como assertion — formaliza em pytest o que
scripts/run_eval.py já faz manualmente, caso a caso, em vez de só medir a
média agregada.

Diferente de test_golden_dataset.py (que testa resolvers SQL puros, sem
LLM): este teste chama o Claude de produção (gerador) e um segundo Claude
(juiz) para cada um dos 15 casos, então requer ANTHROPIC_API_KEY real e tem
custo de tokens — por isso fica atrás do marker `llm_eval`, separado de
`integration`, e fora do addopts padrão.

Nota sobre o caso adversarial "012" (pergunta sobre PETR4, cotação de ação
individual): a expectativa de recusa continua válida mesmo depois de uma
fonte de ingestão para ações individuais existir (ex. brapi.dev) — a
camada de geração (rag_b3.generation.tools.TOOL_SPECS) não expõe nenhuma
tool sobre cotação por papel, só as 7 numéricas do Ibovespa + 2 textuais
CVM. Ingestão de watchlist não é o mesmo que exposição ao RAG."""

import json

import anthropic
import pytest

from rag_b3.config.settings import get_settings
from rag_b3.eval.judge import score_answer_relevancy, score_faithfulness
from rag_b3.generation.answer import answer_question
from tests.integration._golden_dataset import load_cases

pytestmark = pytest.mark.llm_eval

FAITHFULNESS_THRESHOLD = 0.85
RELEVANCY_THRESHOLD = 0.80

ALL_CASES = load_cases()


@pytest.fixture(scope="module")
def gen_client():
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


@pytest.fixture(scope="module")
def judge_client():
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


@pytest.mark.parametrize("case", ALL_CASES, ids=[c["id"] for c in ALL_CASES])
def test_golden_case_generation_quality(conn, gen_client, judge_client, case):
    result = answer_question(conn, case["query"], client=gen_client)
    contexts = [json.dumps(tc["result"], ensure_ascii=False) for tc in result.tool_calls]

    relevancy = score_answer_relevancy(judge_client, case["query"], result.text)
    assert relevancy.score >= RELEVANCY_THRESHOLD, (
        f"caso {case['id']}: answer_relevancy {relevancy.score:.2f} abaixo do "
        f"threshold {RELEVANCY_THRESHOLD} — {relevancy.reasoning}"
    )

    if case.get("resolver") or case.get("requires_retrieval"):
        faithfulness = score_faithfulness(judge_client, case["query"], result.text, contexts)
        unsupported = [c.claim for c in faithfulness.claims if not c.supported]
        assert faithfulness.score >= FAITHFULNESS_THRESHOLD, (
            f"caso {case['id']}: faithfulness {faithfulness.score:.2f} abaixo do "
            f"threshold {FAITHFULNESS_THRESHOLD} — alegações não sustentadas: {unsupported}"
        )
