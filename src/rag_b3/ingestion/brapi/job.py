import logging

from psycopg import Connection

from rag_b3.common.audit import AuditLogger
from rag_b3.common.job_run import JobRunTracker
from rag_b3.common.time_utils import today_sao_paulo
from rag_b3.config.settings import Settings
from rag_b3.config.watchlist import load_watchlist
from rag_b3.ingestion.brapi.client import BrapiClient
from rag_b3.ingestion.brapi.errors import BrapiError
from rag_b3.ingestion.brapi.repository import upsert_stock_quote

logger = logging.getLogger(__name__)


def run_brapi_ingestion(settings: Settings, conn: Connection) -> dict:
    """Job diário de cotação por ticker via brapi.dev — reativa a watchlist
    de ações individuais bloqueada no plano free da HG Brasil (ver
    ingestion/hg_brasil/errors.py:HgBrasilPlanRestrictedError). Diferente da
    HG Brasil, o endpoint aceita a watchlist inteira em 1 única requisição
    (GET /quote/AAA,BBB,...) — sem budget manager por enquanto: o limite do
    brapi free é mensal, não diário, e 1 requisição/dia útil fica bem abaixo
    de limites free típicos. Reavaliar se a validação empírica mostrar o
    contrário (rag_b3.ingestion.hg_brasil.budget_manager é reaproveitável)."""
    tracker = JobRunTracker()
    audit = AuditLogger()
    job_run_id = tracker.start(conn, "brapi")
    conn.commit()

    watchlist = load_watchlist(settings.watchlist_path)
    trade_date = today_sao_paulo()
    summary: dict = {
        "requested": len(watchlist),
        "succeeded": 0,
        "failed": 0,
        "not_found": [],
    }

    if not watchlist:
        tracker.finish(conn, job_run_id, "success", summary)
        conn.commit()
        return summary

    client = BrapiClient(settings.brapi_token)
    try:
        raw = client.get_quotes([t.symbol for t in watchlist])
    except BrapiError as exc:
        audit.log(
            conn,
            source="brapi",
            action="fetch_quotes",
            status="aborted",
            error_code=exc.code,
            raw_response=exc.raw,
            job_run_id=job_run_id,
            metadata={"tickers": [t.symbol for t in watchlist]},
        )
        tracker.finish(conn, job_run_id, "failed", summary)
        conn.commit()
        client.close()
        return summary

    results = raw.get("results") if isinstance(raw, dict) else None
    found_by_symbol = {
        item["symbol"]: item
        for item in (results or [])
        if isinstance(item, dict) and item.get("symbol")
    }

    for ticker in watchlist:
        asset = found_by_symbol.get(ticker.symbol)
        if asset is None:
            summary["not_found"].append(ticker.symbol)
            audit.log(
                conn,
                source="brapi",
                action="fetch_quotes",
                request_ref=ticker.symbol,
                status="error",
                error_code="NOT_FOUND",
                job_run_id=job_run_id,
            )
            conn.commit()
            continue

        try:
            upsert_stock_quote(conn, ticker.symbol, trade_date, job_run_id, asset, raw)
            summary["succeeded"] += 1
            audit.log(
                conn,
                source="brapi",
                action="fetch_quotes",
                request_ref=ticker.symbol,
                status="success",
                raw_response=asset,
                job_run_id=job_run_id,
            )
            conn.commit()
        except Exception:
            logger.exception("Falha ao persistir cotação brapi de %s", ticker.symbol)
            summary["failed"] += 1
            conn.rollback()

    client.close()

    if summary["failed"] == 0 and not summary["not_found"]:
        status = "success"
    elif summary["succeeded"] > 0:
        status = "partial_success"
    else:
        status = "failed"
    tracker.finish(conn, job_run_id, status, summary)
    conn.commit()
    return summary
