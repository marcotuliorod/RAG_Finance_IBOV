import uuid
from datetime import date
from unittest.mock import MagicMock

from rag_b3.ingestion.brapi.repository import upsert_stock_quote
from tests.conftest import load_json_fixture


def test_upsert_stock_quote_parses_and_inserts_into_stock_quote_table():
    fixture = load_json_fixture("brapi_quote_ok.json")
    asset = fixture["results"][0]  # PETR4
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    upsert_stock_quote(conn, "PETR4", date(2026, 7, 10), uuid.uuid4(), asset, fixture)

    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args.args
    assert "insert into stock_quote" in sql
    assert "'brapi'" in sql
    assert params[0] == "PETR4"
    assert params[3] == 38.42  # price


def test_upsert_stock_quote_never_raises_on_unparseable_asset():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    # asset sem os campos esperados — não deve levantar, só gravar None e
    # preservar o raw_response completo (mesmo padrão de
    # hg_brasil/repository.py:upsert_stock_quote).
    upsert_stock_quote(
        conn, "ZZZZ9", date(2026, 7, 10), uuid.uuid4(), {"unexpected": "shape"}, {"raw": "data"}
    )

    cursor.execute.assert_called_once()
