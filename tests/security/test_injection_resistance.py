"""Testes executáveis contra o Postgres real (Docker) provando que tool
inputs adversariais — payloads clássicos de SQL injection, valores fora de
faixa, bytes inválidos, strings gigantes — nunca escapam da query
parametrizada nem derrubam a resposta com uma exceção não tratada. Ver
docs/security/AI_SECURITY.md — Prompt Injection / Tool Abuse. Não depende de
LLM real: chama execute_tool diretamente (o mesmo dispatch que o loop de
tool-use real usa), simulando o pior caso possível de input vindo de um
modelo manipulado."""

from datetime import date

import pytest

from rag_b3.generation.tools import execute_tool
from rag_b3.retrieval.cvm_textual import latest_by_feed

pytestmark = pytest.mark.integration

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE cvm_feed_item; --",
    "' OR '1'='1",
    "1; DELETE FROM ibov_daily_history WHERE 1=1; --",
    "a" * 10_000,  # payload gigante — ver docs/security/AI_SECURITY.md Denial of Wallet
]


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_cvm_search_tool_treats_injection_payloads_as_literal_search_text(conn, payload):
    # Se a query não fosse parametrizada, um payload como o primeiro
    # derrubaria a tabela. Como é parametrizada, o pior que pode acontecer é
    # "nenhum resultado encontrado" — nunca uma segunda instrução SQL executada,
    # e nunca um {"error": ...} inesperado (isso não é um erro de dado
    # insuficiente, é só texto de busca sem match).
    result = execute_tool(conn, "cvm_search", {"query_text": payload})
    assert isinstance(result, list)

    # Prova que a tabela sobreviveu — se o DROP tivesse executado, esta
    # segunda chamada falharia com "relation does not exist".
    sanity_check = execute_tool(
        conn, "cvm_search", {"query_text": "resolução", "feed_key": "legislacao", "limit": 1}
    )
    assert isinstance(sanity_check, list)


def test_cvm_search_tool_handles_null_bytes_as_a_graceful_tool_error_not_a_crash(conn):
    # Achado real (encontrado ao escrever este teste): PostgreSQL/psycopg
    # rejeita bytes NUL em texto com psycopg.DataError. Sem tratamento,
    # isso vazava como exceção não tratada por execute_tool — quebrando o
    # contrato de "todo erro de tool vira {'error': ...} para o LLM ver" e
    # derrubando a resposta inteira com um 500 genérico em vez de deixar o
    # modelo reformular. Corrigido em generation/tools.py — este teste
    # prova que o catch funciona E que a conexão continua utilizável depois
    # (rollback correto, sem deixar a transação em estado abortado).
    result = execute_tool(conn, "cvm_search", {"query_text": "\x00\x01\x02"})
    assert "error" in result

    # A conexão precisa continuar funcional para a próxima rodada de
    # tool-use no mesmo loop (mesma conn reaproveitada por até 5 rodadas).
    follow_up = execute_tool(conn, "ibov_latest_bar", {})
    assert "error" not in follow_up


def test_latest_by_feed_rejects_injection_payload_as_feed_key(conn):
    # feed_key é allowlist-checked (FEED_KEYS) antes de qualquer SQL — um
    # payload de injection como feed_key deve ser rejeitado pela validação
    # de aplicação, nunca chegar à query. Testado na camada de retrieval
    # diretamente (não via execute_tool) porque é aqui que a validação de
    # defesa em profundidade realmente vive.
    with pytest.raises(ValueError):
        latest_by_feed(conn, "legislacao'; DROP TABLE cvm_feed_item; --", limit=1)


def test_ibov_extreme_between_tool_rejects_injection_payload_as_kind(conn):
    # `kind` é interpolado na cláusula ORDER BY (não dá para parametrizar
    # uma palavra-chave SQL) — por isso é validado contra um allowlist
    # ("max"/"min") ANTES de entrar na string da query. Testado via
    # execute_tool para confirmar que o payload nunca escapa do contrato de
    # erro mesmo vindo pelo caminho real que o LLM usaria.
    result = execute_tool(
        conn,
        "ibov_extreme_between",
        {
            "start_date": date(2024, 1, 1).isoformat(),
            "end_date": date(2024, 12, 31).isoformat(),
            "kind": "max; DROP TABLE ibov_daily_history; --",
        },
    )
    assert "error" in result
