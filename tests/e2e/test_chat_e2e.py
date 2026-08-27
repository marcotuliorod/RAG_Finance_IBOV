"""Teste end-to-end real: sobe a aplicação FastAPI de verdade
(create_app()), NÃO faz mock da conexão com o Postgres (usa o banco real
configurado via DATABASE_URL, o mesmo docker-compose.yml usado em dev/CI) —
só a chamada de rede para a API da Anthropic é mockada, para não custar
dinheiro real a cada execução de teste. Isso exercita o caminho real
completo: HTTP -> FastAPI -> answer_question -> execute_tool -> SQL
parametrizada -> Postgres -> serialização -> resposta HTTP.

Usa um período histórico totalmente fechado (2023) para que o resultado
esperado seja estável independente de quando os testes rodam ou de novas
ingestões futuras."""

import pytest
from fastapi.testclient import TestClient

from rag_b3.web.app import _get_client, create_app

pytestmark = pytest.mark.integration


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


class _Usage:
    def __init__(self, input_tokens=1200, output_tokens=180):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content
        self.usage = _Usage()
        self.model = "claude-sonnet-5"


class _FakeAnthropicClient:
    """Simula exatamente o formato real de resposta do SDK Anthropic para
    uma pergunta que exige uma chamada de tool_use seguida de resposta
    final — sem nenhuma chamada de rede real."""

    def __init__(self, tool_name, tool_input, final_text):
        self._responses = [
            _Response(
                "tool_use",
                [_ToolUseBlock("call_1", tool_name, tool_input)],
            ),
            _Response("end_turn", [_TextBlock(final_text)]),
        ]
        self.messages = self

    def create(self, **kwargs):
        return self._responses.pop(0)


def test_full_stack_answers_a_deterministic_historical_period_question():
    fake_client = _FakeAnthropicClient(
        tool_name="ibov_period_summary",
        tool_input={"start_date": "2023-01-01", "end_date": "2023-12-31"},
        final_text=(
            "Em 2023 (248 pregões), o Ibovespa teve variação acumulada de +21,95%, "
            "com máxima de 134.194,00 pontos em 2023-12-27 e mínima de 97.926,00 "
            "pontos em 2023-03-23."
        ),
    )

    app = create_app()
    app.dependency_overrides[_get_client] = lambda: fake_client
    # _get_conn NÃO é sobrescrito — usa a conexão real com o Postgres do
    # docker-compose, exatamente como a aplicação real faria.

    with TestClient(app) as client:
        response = client.post(
            "/api/ask", json={"query": "Como foi o desempenho do Ibovespa em 2023?"}
        )

    assert response.status_code == 200
    data = response.json()

    assert "21,95" in data["answer"] or "21.95" in data["answer"]

    assert len(data["tool_calls"]) == 1
    tool_call = data["tool_calls"][0]
    assert tool_call["name"] == "ibov_period_summary"

    # O resultado da tool veio de uma query SQL real contra o Postgres real
    # — não um mock — então estes valores só batem se o dado real ingerido
    # (Session 1 audit: 2.644 linhas, 2016-01-04 a 2026-08-24) ainda cobrir
    # 2023 corretamente.
    result = tool_call["result"]
    assert result["trading_days"] == 248
    assert result["variation_percent"] == pytest.approx(21.95, abs=0.01)
    assert result["max_close"] == pytest.approx(134194.0, abs=0.01)
    assert result["min_close"] == pytest.approx(97926.0, abs=0.01)


def test_full_stack_returns_insufficient_data_error_from_real_db_for_out_of_range_period():
    fake_client = _FakeAnthropicClient(
        tool_name="ibov_variation_between",
        tool_input={"start_date": "1990-01-01", "end_date": "1990-12-31"},
        final_text="Não tenho dado histórico suficiente para 1990 — a série começa em 2016.",
    )

    app = create_app()
    app.dependency_overrides[_get_client] = lambda: fake_client

    with TestClient(app) as client:
        response = client.post(
            "/api/ask", json={"query": "Qual foi a variação do Ibovespa em 1990?"}
        )

    assert response.status_code == 200
    data = response.json()
    tool_call = data["tool_calls"][0]
    # Erro real vindo do banco real (InsufficientDataError, não um mock) —
    # prova que o contrato de "tool error vira {'error': ...}" funciona
    # ponta a ponta, não só em teste unitário isolado.
    assert "error" in tool_call["result"]
