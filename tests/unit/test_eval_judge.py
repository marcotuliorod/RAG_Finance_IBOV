from unittest.mock import MagicMock

from rag_b3.eval.judge import score_answer_relevancy, score_faithfulness


class _ToolUseBlock:
    def __init__(self, name, input_):
        self.type = "tool_use"
        self.name = name
        self.input = input_


class _Response:
    def __init__(self, content):
        self.content = content


def test_score_faithfulness_computes_ratio_of_supported_claims():
    client = MagicMock()
    client.messages.create.return_value = _Response(
        [
            _ToolUseBlock(
                "submit_faithfulness_evaluation",
                {
                    "claims": [
                        {"claim": "Ibovespa fechou em 177.866,38", "supported": True},
                        {"claim": "variação foi de +2,97%", "supported": True},
                        {"claim": "isso é uma cotação em tempo real", "supported": False},
                    ]
                },
            )
        ]
    )

    result = score_faithfulness(
        client,
        question="qual a pontuação atual?",
        answer="177.866,38 pontos, +2,97%, tempo real",
        contexts=['{"trade_date": "2026-07-11", "close": 177866.38}'],
    )

    assert result.score == 2 / 3
    assert len(result.claims) == 3
    client.messages.create.assert_called_once()
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-8"
    assert call_kwargs["tool_choice"] == {
        "type": "tool",
        "name": "submit_faithfulness_evaluation",
    }


def test_score_faithfulness_empty_claims_is_vacuously_faithful():
    client = MagicMock()
    client.messages.create.return_value = _Response(
        [_ToolUseBlock("submit_faithfulness_evaluation", {"claims": []})]
    )

    result = score_faithfulness(
        client, question="você recomenda comprar?", answer="não posso recomendar isso.", contexts=[]
    )

    assert result.score == 1.0
    assert result.claims == []


def test_score_answer_relevancy_returns_score_and_reasoning():
    client = MagicMock()
    client.messages.create.return_value = _Response(
        [
            _ToolUseBlock(
                "submit_relevancy_evaluation",
                {"score": 0.95, "reasoning": "Responde diretamente à pergunta."},
            )
        ]
    )

    result = score_answer_relevancy(
        client, question="qual a variação em 2023?", answer="+21,95% em 2023."
    )

    assert result.score == 0.95
    assert "diretamente" in result.reasoning
    call_kwargs = client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-8"
