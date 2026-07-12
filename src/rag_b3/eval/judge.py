"""LLM-as-judge para faithfulness e answer relevancy (métricas/thresholds de
constitution.md: faithfulness ≥ 0.85, answer relevancy ≥ 0.80).

Implementação própria em vez do pacote `ragas`: `ragas==0.4.3` tem um import
quebrado (`langchain_community.chat_models.vertexai`, removido em versões
recentes do `langchain-community`) que não se resolve nem instalando o
pacote de integração do Vertex — só isso já puxa uma cadeia grande de
dependências do Google Cloud. A técnica (LLM-as-judge decompondo a resposta
em alegações e verificando suporte no contexto) é a mesma; só não usamos o
framework. Reavaliar se uma versão futura do ragas corrigir o import.

Juiz: claude-opus-4-8 — nunca o mesmo modelo usado para gerar a resposta
avaliada (evita identity bias), conforme constitution.md."""

import anthropic

from rag_b3.eval.models import ClaimJudgement, FaithfulnessResult, RelevancyResult

JUDGE_MODEL = "claude-opus-4-8"

_FAITHFULNESS_TOOL = {
    "name": "submit_faithfulness_evaluation",
    "description": "Registra a avaliação de faithfulness de uma resposta.",
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "description": "Alegações factuais atômicas extraídas da resposta. Se a "
                "resposta não fizer nenhuma alegação factual (ex.: recusa, pedido de "
                "esclarecimento), retorne uma lista vazia.",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "supported": {
                            "type": "boolean",
                            "description": "true se o contexto fornecido sustenta a alegação",
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": ["claim", "supported"],
                },
            },
        },
        "required": ["claims"],
    },
}

_RELEVANCY_TOOL = {
    "name": "submit_relevancy_evaluation",
    "description": "Registra a avaliação de relevância de uma resposta para a pergunta.",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "0.0 = não responde à pergunta / totalmente fora do tópico; "
                "1.0 = responde direta e completamente à pergunta, sem informação "
                "irrelevante. Recusas apropriadas (fora de escopo, dado insuficiente) "
                "contam como altamente relevantes se comunicam isso claramente.",
            },
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
    },
}


def _call_judge_tool(client: anthropic.Anthropic, system: str, user: str, tool: dict) -> dict:
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=2048,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"Juiz não retornou tool_use para {tool['name']}")


def score_faithfulness(
    client: anthropic.Anthropic, question: str, answer: str, contexts: list[str]
) -> FaithfulnessResult:
    context_text = "\n\n".join(contexts) if contexts else "(nenhum contexto/ferramenta usado)"
    user = f"""Pergunta original: {question}

Contexto disponível (resultado das ferramentas chamadas para responder):
{context_text}

Resposta a avaliar:
{answer}

Extraia as alegações factuais atômicas da resposta e julgue se cada uma é
sustentada pelo contexto acima. Não julgue se a alegação é verdadeira em
geral — apenas se o contexto fornecido a sustenta. Recusas/pedidos de
esclarecimento sem alegação factual devem ter lista de claims vazia."""

    result = _call_judge_tool(
        client,
        system="Você é um avaliador rigoroso de faithfulness para um sistema RAG.",
        user=user,
        tool=_FAITHFULNESS_TOOL,
    )
    claims = [ClaimJudgement(**c) for c in result["claims"]]
    score = sum(c.supported for c in claims) / len(claims) if claims else 1.0
    return FaithfulnessResult(claims=claims, score=score)


def score_answer_relevancy(
    client: anthropic.Anthropic, question: str, answer: str
) -> RelevancyResult:
    user = f"""Pergunta original: {question}

Resposta a avaliar:
{answer}

Avalie o quão relevante e direta a resposta é em relação à pergunta."""

    result = _call_judge_tool(
        client,
        system="Você é um avaliador rigoroso de answer relevancy para um sistema RAG.",
        user=user,
        tool=_RELEVANCY_TOOL,
    )
    return RelevancyResult(score=result["score"], reasoning=result["reasoning"])
