import httpx
import pytest
import respx

from rag_b3.ingestion.hg_brasil.budget_manager import BudgetManager, QuotaExceededError
from rag_b3.ingestion.hg_brasil.client import BASE_URL, HgBrasilClient
from rag_b3.ingestion.hg_brasil.errors import (
    HgBrasilAuthError,
    HgBrasilPlanRestrictedError,
    HgBrasilPossibleQuotaExceeded,
    HgBrasilTickerError,
    HgBrasilUnknownError,
)
from tests.conftest import InMemoryBudgetRepository, load_json_fixture


def _make_client(effective_limit: int = 360) -> HgBrasilClient:
    manager = BudgetManager(InMemoryBudgetRepository(effective_limit=effective_limit))
    return HgBrasilClient(api_key="dummy-key", budget=manager)


@respx.mock
def test_get_stock_price_ok():
    fixture = load_json_fixture("hg_brasil_stock_price_ok.json")
    respx.get(f"{BASE_URL}/stock_price").mock(return_value=httpx.Response(200, json=fixture))

    client = _make_client()
    data = client.get_stock_price("PETR4")
    assert data["results"]["PETR4"]["price"] == 38.42


@respx.mock
def test_get_market_snapshot_ok():
    fixture = load_json_fixture("hg_brasil_finance_ok.json")
    respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, json=fixture))

    client = _make_client()
    data = client.get_market_snapshot()
    assert data["results"]["stocks"]["IBOVESPA"]["points"] == 132456.78


@respx.mock
def test_invalid_ticker_raises_non_fatal_error_and_does_not_retry():
    fixture = load_json_fixture("hg_brasil_error_invalid_ticker.json")
    route = respx.get(f"{BASE_URL}/stock_price").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    client = _make_client()
    with pytest.raises(HgBrasilTickerError):
        client.get_stock_price("XXXX0")
    # não deve ter tentado de novo — erro de aplicação não é transitório
    assert route.call_count == 1


@respx.mock
def test_invalid_api_key_raises_fatal_auth_error():
    fixture = load_json_fixture("hg_brasil_error_invalid_key.json")
    respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(200, json=fixture))

    client = _make_client()
    with pytest.raises(HgBrasilAuthError):
        client.get_market_snapshot()


@respx.mock
def test_http_429_raises_possible_quota_exceeded_without_retry():
    route = respx.get(f"{BASE_URL}/").mock(return_value=httpx.Response(429))

    client = _make_client()
    with pytest.raises(HgBrasilPossibleQuotaExceeded):
        client.get_market_snapshot()
    assert route.call_count == 1


@respx.mock
def test_transient_5xx_is_retried_then_succeeds():
    fixture = load_json_fixture("hg_brasil_finance_ok.json")
    route = respx.get(f"{BASE_URL}/").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=fixture),
        ]
    )

    client = _make_client(effective_limit=360)
    data = client.get_market_snapshot()
    assert data["results"]["stocks"]["IBOVESPA"]["points"] == 132456.78
    assert route.call_count == 2


@respx.mock
def test_unknown_error_code_is_not_fatal_and_not_retried():
    fixture = load_json_fixture("hg_brasil_error_unknown_code.json")
    route = respx.get(f"{BASE_URL}/stock_price").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    client = _make_client()
    with pytest.raises(HgBrasilUnknownError):
        client.get_stock_price("PETR4")
    assert route.call_count == 1


@respx.mock
def test_plan_restricted_response_raises_and_is_not_retried():
    # Confirmado ao vivo em 2026-07-11: /finance/stock_price responde HTTP
    # 200 com {"results": {"error": true, "message": "..."}} no plano free,
    # para qualquer símbolo — não está no catálogo de errors[] documentado.
    fixture = load_json_fixture("hg_brasil_error_plan_restricted.json")
    route = respx.get(f"{BASE_URL}/stock_price").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    client = _make_client()
    with pytest.raises(HgBrasilPlanRestrictedError):
        client.get_stock_price("PETR4")
    assert route.call_count == 1


@respx.mock
def test_each_retry_reserves_budget_again():
    fixture = load_json_fixture("hg_brasil_finance_ok.json")
    respx.get(f"{BASE_URL}/").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=fixture),
        ]
    )
    # orçamento só permite 1 reserva -> a 2ª tentativa (retry) deve estourar
    client = _make_client(effective_limit=1)
    with pytest.raises(QuotaExceededError):
        client.get_market_snapshot()
