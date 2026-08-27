import httpx
import pytest
import respx

from rag_b3.ingestion.brapi.client import BASE_URL, BrapiClient
from rag_b3.ingestion.brapi.errors import (
    BrapiAuthError,
    BrapiPossibleQuotaExceeded,
    BrapiRequestError,
)
from tests.conftest import load_json_fixture


def _make_client(token: str | None = "dummy-token") -> BrapiClient:
    return BrapiClient(token=token)


@respx.mock
def test_get_quotes_ok():
    fixture = load_json_fixture("brapi_quote_ok.json")
    respx.get(f"{BASE_URL}/quote/PETR4,VALE3").mock(return_value=httpx.Response(200, json=fixture))

    client = _make_client()
    data = client.get_quotes(["PETR4", "VALE3"])
    assert data["results"][0]["symbol"] == "PETR4"
    assert data["results"][1]["regularMarketPrice"] == 61.10


@respx.mock
def test_get_quotes_without_token_for_free_tickers():
    fixture = load_json_fixture("brapi_quote_ok.json")
    route = respx.get(f"{BASE_URL}/quote/PETR4,VALE3").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    client = _make_client(token=None)
    client.get_quotes(["PETR4", "VALE3"])
    # sem token, nenhum query param "token" deve ser enviado
    assert "token" not in route.calls.last.request.url.params


@respx.mock
def test_invalid_token_raises_fatal_auth_error():
    respx.get(f"{BASE_URL}/quote/PETR4").mock(return_value=httpx.Response(401))

    client = _make_client()
    with pytest.raises(BrapiAuthError):
        client.get_quotes(["PETR4"])


@respx.mock
def test_forbidden_raises_fatal_auth_error():
    respx.get(f"{BASE_URL}/quote/PETR4").mock(return_value=httpx.Response(403))

    client = _make_client()
    with pytest.raises(BrapiAuthError):
        client.get_quotes(["PETR4"])


@respx.mock
def test_error_body_raises_request_error_without_retry():
    fixture = load_json_fixture("brapi_error_invalid_token.json")
    route = respx.get(f"{BASE_URL}/quote/XXXX0").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    client = _make_client()
    with pytest.raises(BrapiRequestError):
        client.get_quotes(["XXXX0"])
    assert route.call_count == 1


@respx.mock
def test_http_429_raises_possible_quota_exceeded_without_retry():
    route = respx.get(f"{BASE_URL}/quote/PETR4").mock(return_value=httpx.Response(429))

    client = _make_client()
    with pytest.raises(BrapiPossibleQuotaExceeded):
        client.get_quotes(["PETR4"])
    assert route.call_count == 1


@respx.mock
def test_transient_5xx_is_retried_then_succeeds():
    fixture = load_json_fixture("brapi_quote_ok.json")
    route = respx.get(f"{BASE_URL}/quote/PETR4,VALE3").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=fixture)]
    )

    client = _make_client()
    data = client.get_quotes(["PETR4", "VALE3"])
    assert data["results"][0]["symbol"] == "PETR4"
    assert route.call_count == 2


@respx.mock
def test_not_found_raises_request_error_without_retry():
    route = respx.get(f"{BASE_URL}/quote/XXXX0").mock(return_value=httpx.Response(404))

    client = _make_client()
    with pytest.raises(BrapiRequestError):
        client.get_quotes(["XXXX0"])
    assert route.call_count == 1
