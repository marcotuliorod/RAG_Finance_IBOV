from datetime import date

import httpx
import pytest
import respx

from rag_b3.ingestion.yahoo_finance.client import (
    BASE_URL,
    IBOV_SYMBOL,
    YahooFinanceError,
    fetch_ibov_chart,
    parse_ibov_chart,
)
from tests.conftest import load_json_fixture


@respx.mock
def test_fetch_ibov_chart_ok():
    fixture = load_json_fixture("yahoo_finance_chart_ok.json")
    respx.get(f"{BASE_URL}/{IBOV_SYMBOL}").mock(return_value=httpx.Response(200, json=fixture))

    data = fetch_ibov_chart(range_="10y")
    assert data["chart"]["result"][0]["meta"]["symbol"] == "^BVSP"


@respx.mock
def test_fetch_ibov_chart_5xx_is_retried():
    fixture = load_json_fixture("yahoo_finance_chart_ok.json")
    route = respx.get(f"{BASE_URL}/{IBOV_SYMBOL}").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=fixture)]
    )
    data = fetch_ibov_chart()
    assert data["chart"]["result"][0]["meta"]["symbol"] == "^BVSP"
    assert route.call_count == 2


@respx.mock
def test_fetch_ibov_chart_error_payload_raises():
    respx.get(f"{BASE_URL}/{IBOV_SYMBOL}").mock(
        return_value=httpx.Response(200, json={"chart": {"result": None, "error": {"code": "Not Found"}}})
    )
    with pytest.raises(YahooFinanceError):
        fetch_ibov_chart()


def test_parse_ibov_chart_skips_bars_without_close():
    fixture = load_json_fixture("yahoo_finance_chart_ok.json")
    bars = parse_ibov_chart(fixture)

    # o 3º timestamp tem close=null (candle do dia ainda se formando) — deve
    # ser descartado, não inventado.
    assert len(bars) == 2
    assert bars[0].trade_date == date(2025, 6, 30)
    assert bars[0].close == 136500.0
    assert bars[0].variation_percent is None  # primeira barra não tem anterior
    assert bars[1].close == 137000.0
    assert bars[1].variation_percent == pytest.approx((137000.0 - 136500.0) / 136500.0 * 100)


def test_parse_ibov_chart_malformed_raises():
    with pytest.raises(YahooFinanceError):
        parse_ibov_chart({"chart": {"result": []}})
