"""Verificação estrutural (não substitui avaliação com LLM real) de que o
system prompt ainda contém as regras de grounding/recusa que sustentam os
achados de faithfulness deste projeto (docs/evaluation/baseline.md) e a
análise de ameaças em docs/security/AI_SECURITY.md. Existe para que uma
edição futura no prompt que remova uma dessas regras falhe um teste em vez
de só ser descoberta na próxima rodada (cara, paga) de scripts/run_eval.py."""

from rag_b3.generation.prompt import SYSTEM_PROMPT


def test_prompt_forbids_mental_math():
    assert "NUNCA calcule" in SYSTEM_PROMPT


def test_prompt_forbids_speculation_on_tool_error():
    assert "Nunca estime ou invente um valor" in SYSTEM_PROMPT


def test_prompt_requires_citation_for_numeric_claims():
    assert "trade_date" in SYSTEM_PROMPT
    assert "source" in SYSTEM_PROMPT


def test_prompt_requires_citation_for_cvm_claims():
    assert "título, data de" in SYSTEM_PROMPT
    assert "link" in SYSTEM_PROMPT


def test_prompt_refuses_individual_stock_quotes():
    assert "ações individuais" in SYSTEM_PROMPT


def test_prompt_refuses_investment_recommendations():
    assert "Recomendação de investimento" in SYSTEM_PROMPT


def test_prompt_refuses_future_predictions():
    assert "Previsão de valores futuros" in SYSTEM_PROMPT


def test_prompt_instructs_admitting_uncertainty():
    assert "Nunca especule" in SYSTEM_PROMPT
