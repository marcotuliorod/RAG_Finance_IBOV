import json
import logging
import uuid
from datetime import date
from typing import Any

from psycopg import Connection

from rag_b3.ingestion.hg_brasil.models import StockPrice

logger = logging.getLogger(__name__)


def _dig(d: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def extract_ibovespa_close_and_variation(raw: dict) -> tuple[float | None, float | None]:
    """Extrai points/variation do IBOVESPA do payload do endpoint principal
    /finance — usado pelo job para alimentar ibov_daily_history (fonte
    única de série histórica do índice, ver yahoo_finance/repository.py)."""
    results = raw.get("results", {}) if isinstance(raw, dict) else {}
    return _dig(results, "stocks", "IBOVESPA", "points"), _dig(results, "stocks", "IBOVESPA", "variation")


def _extract_taxes(taxes: Any) -> tuple[float | None, float | None]:
    """taxes vem como LISTA de snapshots diários na API real observada
    (ex.: [{"date": "...", "cdi": 14.25, "selic": 14.25, ...}]) — não como
    dict {"CDI": ..., "SELIC": ...} como a documentação pública sugeria.
    Mantemos o fallback de dict por segurança, mas a lista é o formato real."""
    if isinstance(taxes, list) and taxes:
        latest = taxes[0]
        if isinstance(latest, dict):
            return latest.get("cdi"), latest.get("selic")
        return None, None
    if isinstance(taxes, dict):
        cdi = taxes.get("cdi") or taxes.get("CDI")
        selic = taxes.get("selic") or taxes.get("SELIC")

        def _rate(value: Any) -> float | None:
            if isinstance(value, dict):
                return value.get("value") or value.get("rate")
            return value if isinstance(value, (int, float)) else None

        return _rate(cdi), _rate(selic)
    return None, None


def _extract_snapshot_fields(raw: dict) -> dict:
    """Extração best-effort dos campos do endpoint principal /finance. A
    documentação pública não detalha o shape exato de stocks/currencies/taxes
    — falha de extração de um campo não impede os demais nem descarta o
    raw_response, que é sempre persistido por completo."""
    results = raw.get("results", {}) if isinstance(raw, dict) else {}
    cdi_rate, selic_rate = _extract_taxes(results.get("taxes") if isinstance(results, dict) else None)

    return {
        "ibovespa_points": _dig(results, "stocks", "IBOVESPA", "points"),
        "ifix_points": _dig(results, "stocks", "IFIX", "points"),
        "usd_brl": _dig(results, "currencies", "USD", "buy"),
        "cdi_rate": cdi_rate,
        "selic_rate": selic_rate,
    }


def upsert_market_snapshot(
    conn: Connection,
    snapshot_date: date,
    job_run_id: uuid.UUID,
    raw_response: dict,
) -> None:
    fields = _extract_snapshot_fields(raw_response)
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into hg_brasil_market_snapshot
                (snapshot_date, job_run_id, ibovespa_points, ifix_points,
                 usd_brl, cdi_rate, selic_rate, raw_response)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (snapshot_date) do update set
                job_run_id = excluded.job_run_id,
                ibovespa_points = excluded.ibovespa_points,
                ifix_points = excluded.ifix_points,
                usd_brl = excluded.usd_brl,
                cdi_rate = excluded.cdi_rate,
                selic_rate = excluded.selic_rate,
                raw_response = excluded.raw_response,
                captured_at = now()
            """,
            (
                snapshot_date,
                job_run_id,
                fields["ibovespa_points"],
                fields["ifix_points"],
                fields["usd_brl"],
                fields["cdi_rate"],
                fields["selic_rate"],
                json.dumps(raw_response),
            ),
        )


def _extract_asset_dict(raw: dict, symbol: str) -> dict | None:
    results = raw.get("results") if isinstance(raw, dict) else None
    if isinstance(results, dict):
        if "price" in results:
            return results
        return results.get(symbol) or (next(iter(results.values()), None))
    if isinstance(results, list) and results:
        return results[0]
    return None


def upsert_stock_quote(
    conn: Connection,
    symbol: str,
    trade_date: date,
    job_run_id: uuid.UUID,
    raw_response: dict,
) -> None:
    asset = _extract_asset_dict(raw_response, symbol)
    parsed: StockPrice | None = None
    if asset:
        try:
            parsed = StockPrice(**{**asset, "symbol": asset.get("symbol", symbol)})
        except Exception:
            logger.warning("Falha ao parsear StockPrice para %s — raw_response preservado", symbol)

    with conn.cursor() as cur:
        cur.execute(
            """
            insert into hg_brasil_stock_quote
                (symbol, trade_date, job_run_id, price, change_percent, change_price,
                 volume, market_cap, currency, region, market_time, api_updated_at,
                 raw_response)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (symbol, trade_date) do update set
                job_run_id = excluded.job_run_id,
                price = excluded.price,
                change_percent = excluded.change_percent,
                change_price = excluded.change_price,
                volume = excluded.volume,
                market_cap = excluded.market_cap,
                currency = excluded.currency,
                region = excluded.region,
                market_time = excluded.market_time,
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
                parsed.region if parsed else None,
                parsed.market_time if parsed else None,
                parsed.updated_at if parsed else None,
                json.dumps(raw_response),
            ),
        )
