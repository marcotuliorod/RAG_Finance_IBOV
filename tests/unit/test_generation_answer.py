from unittest.mock import MagicMock

import pytest

from rag_b3.generation.answer import GenerationLoopExceededError, answer_question


class _TextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _ToolUseBlock:
    def __init__(self, id_, name, input_):
        self.type = "tool_use"
        self.id = id_
        self.name = name
        self.input = input_


class _Response:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


def test_answer_question_returns_text_when_no_tool_needed():
    client = MagicMock()
    client.messages.create.return_value = _Response(
        "end_turn", [_TextBlock("O Ibovespa é um índice, não recomendo compra/venda.")]
    )

    result = answer_question(MagicMock(), "você recomenda comprar ações?", client=client)

    assert "não recomendo" in result.text
    assert result.tool_calls == []
    client.messages.create.assert_called_once()


def test_answer_question_executes_tool_and_returns_final_text(monkeypatch):
    monkeypatch.setattr(
        "rag_b3.generation.answer.execute_tool",
        lambda conn, name, tool_input: {"trade_date": "2026-07-11", "close": 177866.38},
    )

    client = MagicMock()
    client.messages.create.side_effect = [
        _Response(
            "tool_use",
            [_ToolUseBlock("call_1", "ibov_latest_bar", {})],
        ),
        _Response(
            "end_turn",
            [_TextBlock("Pregão de 2026-07-11: 177.866,38 pontos (fonte: HG Brasil).")],
        ),
    ]

    result = answer_question(MagicMock(), "qual a pontuação atual do Ibovespa?", client=client)

    assert "177.866,38" in result.text
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "ibov_latest_bar"
    assert client.messages.create.call_count == 2

    second_call_messages = client.messages.create.call_args_list[1].kwargs["messages"]
    tool_result_message = second_call_messages[-1]
    assert tool_result_message["role"] == "user"
    assert tool_result_message["content"][0]["type"] == "tool_result"
    assert tool_result_message["content"][0]["tool_use_id"] == "call_1"


def test_answer_question_raises_when_tool_use_loop_never_ends(monkeypatch):
    monkeypatch.setattr(
        "rag_b3.generation.answer.execute_tool",
        lambda conn, name, tool_input: {"trade_date": "2026-07-11", "close": 177866.38},
    )

    client = MagicMock()
    client.messages.create.return_value = _Response(
        "tool_use", [_ToolUseBlock("call_x", "ibov_latest_bar", {})]
    )

    with pytest.raises(GenerationLoopExceededError):
        answer_question(MagicMock(), "loop infinito", client=client)
