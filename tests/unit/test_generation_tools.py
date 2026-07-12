from datetime import date
from unittest.mock import MagicMock


from rag_b3.generation.tools import execute_tool
from rag_b3.query.errors import InsufficientDataError
from rag_b3.query.models import IbovBar, PeriodSummary, VariationResult
from rag_b3.retrieval.models import CvmFeedResult


def _bar(trade_date=date(2026, 7, 11), close=177866.38):
    return IbovBar(
        trade_date=trade_date,
        open=None,
        high=None,
        low=None,
        close=close,
        volume=None,
        variation_percent=2.97,
        source="hg_brasil",
    )


def test_ibov_latest_bar_dispatches_and_serializes(monkeypatch):
    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.get_latest_bar", lambda conn: _bar()
    )
    result = execute_tool(MagicMock(), "ibov_latest_bar", {})
    assert result["trade_date"] == "2026-07-11"
    assert result["close"] == 177866.38


def test_ibov_variation_between_converts_date_strings(monkeypatch):
    captured = {}

    def fake_variation_between(conn, start_date, end_date):
        captured["start_date"] = start_date
        captured["end_date"] = end_date
        return VariationResult(
            start=_bar(date(2026, 1, 1), 100.0),
            end=_bar(date(2026, 2, 1), 110.0),
            variation_percent=10.0,
            variation_points=10.0,
        )

    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.variation_between", fake_variation_between
    )
    result = execute_tool(
        MagicMock(),
        "ibov_variation_between",
        {"start_date": "2026-01-01", "end_date": "2026-02-01"},
    )
    assert captured["start_date"] == date(2026, 1, 1)
    assert captured["end_date"] == date(2026, 2, 1)
    assert result["variation_percent"] == 10.0


def test_insufficient_data_error_becomes_error_dict(monkeypatch):
    def raise_insufficient(conn, start_date, end_date):
        raise InsufficientDataError("sem dado para 1990")

    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.variation_between", raise_insufficient
    )
    result = execute_tool(
        MagicMock(),
        "ibov_variation_between",
        {"start_date": "1990-01-01", "end_date": "1990-12-31"},
    )
    assert "error" in result
    assert "sem dado" in result["error"]


def test_invalid_kind_value_error_becomes_error_dict(monkeypatch):
    def raise_value_error(conn, start_date, end_date, kind):
        raise ValueError("kind deve ser 'max' ou 'min'")

    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.extreme_between", raise_value_error
    )
    result = execute_tool(
        MagicMock(),
        "ibov_extreme_between",
        {"start_date": "2022-01-01", "end_date": "2022-12-31", "kind": "bogus"},
    )
    assert "error" in result


def test_compare_periods_builds_nested_kwargs(monkeypatch):
    captured = {}

    def fake_compare(conn, period_a, period_b):
        captured["period_a"] = period_a
        captured["period_b"] = period_b
        return {
            "summary_a": PeriodSummary(
                start_date=period_a["start_date"],
                end_date=period_a["end_date"],
                trading_days=1,
                variation_percent=1.0,
                max_close=1.0,
                max_close_date=period_a["start_date"],
                min_close=1.0,
                min_close_date=period_a["start_date"],
                average_close=1.0,
            ),
            "summary_b": PeriodSummary(
                start_date=period_b["start_date"],
                end_date=period_b["end_date"],
                trading_days=1,
                variation_percent=-1.0,
                max_close=1.0,
                max_close_date=period_b["start_date"],
                min_close=1.0,
                min_close_date=period_b["start_date"],
                average_close=1.0,
            ),
            "melhor": "a",
            "diferenca_pp": 2.0,
        }

    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.compare_period_summaries", fake_compare
    )
    result = execute_tool(
        MagicMock(),
        "ibov_compare_periods",
        {
            "period_a_start": "2023-01-01",
            "period_a_end": "2023-12-31",
            "period_b_start": "2024-01-01",
            "period_b_end": "2024-12-31",
        },
    )
    assert captured["period_a"]["start_date"] == date(2023, 1, 1)
    assert captured["period_b"]["end_date"] == date(2024, 12, 31)
    assert result["melhor"] == "a"
    assert result["summary_a"]["start_date"] == "2023-01-01"


def test_cvm_latest_by_feed_dispatches(monkeypatch):
    monkeypatch.setattr(
        "rag_b3.generation.tools.cvm_textual.latest_by_feed",
        lambda conn, feed_key, limit: [
            CvmFeedResult(
                feed_key=feed_key,
                title="Resolução CVM 237",
                summary=None,
                link="http://example.com",
                published_at=None,
            )
        ],
    )
    result = execute_tool(MagicMock(), "cvm_latest_by_feed", {"feed_key": "legislacao"})
    assert result[0]["feed_key"] == "legislacao"
    assert result[0]["title"] == "Resolução CVM 237"


def test_cvm_search_invalid_feed_key_becomes_error_dict(monkeypatch):
    def raise_value_error(conn, query_text, feed_key, limit):
        raise ValueError(f"feed_key inválido: {feed_key!r}")

    monkeypatch.setattr(
        "rag_b3.generation.tools.cvm_textual.search_cvm_items", raise_value_error
    )
    result = execute_tool(
        MagicMock(),
        "cvm_search",
        {"query_text": "resolução", "feed_key": "noticias_mercado"},
    )
    assert "error" in result


def test_unknown_tool_name_returns_error_dict():
    result = execute_tool(MagicMock(), "ferramenta_inexistente", {})
    assert "error" in result


def test_none_result_becomes_error_dict(monkeypatch):
    monkeypatch.setattr(
        "rag_b3.generation.tools.ibov_numeric.get_latest_bar", lambda conn: None
    )
    result = execute_tool(MagicMock(), "ibov_latest_bar", {})
    assert "error" in result
