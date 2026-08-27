import json
import logging
import uuid
from datetime import date

from psycopg import Connection

from rag_b3.ingestion.brapi.models import StockQuote

logger = logging.getLogger(__name__)


def upsert_stock_quote(
    conn: Connection,
    symbol: str,
    trade_date: date,
    job_run_id: uuid.UUID,
    asset: dict,
    raw_response: dict,
) -> None:
    """Grava a cotação de um ticker vinda do brapi.dev na tabela
    compartilhada `stock_quote` (source='brapi', ver
    db/migrations/0010_brapi_stock_quote.sql). `asset` é o item já extraído
    de raw_response["results"] para este symbol; `raw_response` (a resposta
    em lote da watchlist inteira) é persistido por completo por ticker, para
    auditoria — igual ao padrão de hg_brasil/repository.py."""
    try:
        parsed: StockQuote | None = StockQuote(**asset)
    except Exception:
        logger.warning("Falha ao parsear StockQuote para %s — raw_response preservado", symbol)
        parsed = None

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into stock_quote
                (symbol, trade_date, source, job_run_id, price, change_percent,
                 change_price, volume, market_cap, currency, api_updated_at,
                 raw_response)
            values (%s, %s, 'brapi', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (symbol, trade_date, source) do update set
                job_run_id = excluded.job_run_id,
                price = excluded.price,
                change_percent = excluded.change_percent,
                change_price = excluded.change_price,
                volume = excluded.volume,
                market_cap = excluded.market_cap,
                currency = excluded.currency,
                api_updated_at = excluded.api_updated_at,
                raw_response = excluded.raw_response,
                ingested_at = now()
            """,
            (
                symbol,
                trade_date,
                job_run_id,
                parsed.price if parsed else None,
                parsed.change_percent if parsed else None,
                parsed.change_price if parsed else None,
                parsed.volume if parsed else None,
                parsed.market_cap if parsed else None,
                parsed.currency if parsed else None,
                parsed.api_updated_at if parsed else None,
                json.dumps(raw_response),
            ),
        )
