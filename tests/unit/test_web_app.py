from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from rag_b3.generation.answer import AnswerResult, GenerationLoopExceededError
from rag_b3.web.app import _get_client, _get_conn, create_app


def test_index_returns_html_page():
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "RAG Ibovespa" in response.text


def test_ask_returns_answer_and_tool_calls(monkeypatch):
    app = create_app()
    app.dependency_overrides[_get_conn] = lambda: MagicMock()
    app.dependency_overrides[_get_client] = lambda: MagicMock()

    monkeypatch.setattr(
        "rag_b3.web.app.answer_question",
        lambda conn, query, client: AnswerResult(
            text="177.866,38 pontos, +2,97% no dia.",
            tool_calls=[{"name": "ibov_latest_bar", "input": {}, "result": {"close": 177866.38}}],
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "qual a pontuação atual?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "177.866,38 pontos, +2,97% no dia."
    assert data["tool_calls"][0]["name"] == "ibov_latest_bar"
    assert data["tool_calls"][0]["result"] == {"close": 177866.38}


def test_ask_rejects_missing_query_field():
    app = create_app()
    app.dependency_overrides[_get_conn] = lambda: MagicMock()
    app.dependency_overrides[_get_client] = lambda: MagicMock()

    with TestClient(app) as client:
        response = client.post("/api/ask", json={})

    assert response.status_code == 422


def test_ask_returns_502_on_generation_loop_exceeded(monkeypatch):
    app = create_app()
    app.dependency_overrides[_get_conn] = lambda: MagicMock()
    app.dependency_overrides[_get_client] = lambda: MagicMock()

    def raise_exceeded(conn, query, client):
        raise GenerationLoopExceededError("Excedeu 5 rodadas de tool-use sem resposta final")

    monkeypatch.setattr("rag_b3.web.app.answer_question", raise_exceeded)

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "loop infinito"})

    assert response.status_code == 502
    assert "Excedeu" in response.json()["detail"]
