import logging

from psycopg import Connection

from rag_b3.common.audit import AuditLogger
from rag_b3.common.job_run import JobRunTracker
from rag_b3.ingestion.yahoo_finance.client import YahooFinanceError, fetch_ibov_chart, parse_ibov_chart
from rag_b3.ingestion.yahoo_finance.repository import upsert_backfill_bar

logger = logging.getLogger(__name__)


def run_ibov_backfill(conn: Connection, range_: str = "10y") -> dict:
    """Backfill retroativo de série histórica diária do Ibovespa via Yahoo
    Finance chart API. Idempotente — pode ser rodado de novo sem duplicar
    ou sobrescrever dias já ingeridos (ver repository.upsert_backfill_bar)."""
    tracker = JobRunTracker()
    audit = AuditLogger()
    job_run_id = tracker.start(conn, "yahoo_finance_backfill")
    conn.commit()

    summary = {"range": range_, "bars_found": 0, "bars_new": 0, "bars_duplicate": 0}

    try:
        raw = fetch_ibov_chart(range_=range_)
        bars = parse_ibov_chart(raw)
    except YahooFinanceError as exc:
        logger.error("Falha no backfill do Ibovespa: %s", exc)
        audit.log(
            conn,
            source="yahoo_finance_backfill",
            action="fetch_chart",
            status="error",
            job_run_id=job_run_id,
            metadata={"range": range_, "error": str(exc)},
        )
        tracker.finish(conn, job_run_id, "failed", summary)
        conn.commit()
        return summary

    summary["bars_found"] = len(bars)
    for bar in bars:
        inserted = upsert_backfill_bar(conn, bar, job_run_id, raw_payload=bar.model_dump(mode="json"))
        if inserted:
            summary["bars_new"] += 1
        else:
            summary["bars_duplicate"] += 1
    conn.commit()

    audit.log(
        conn,
        source="yahoo_finance_backfill",
        action="fetch_chart",
        status="success",
        raw_response=raw,
        job_run_id=job_run_id,
        metadata={
            "range": range_,
            "bars_found": summary["bars_found"],
            "bars_new": summary["bars_new"],
            "bars_duplicate": summary["bars_duplicate"],
        },
    )
    tracker.finish(conn, job_run_id, "success", summary)
    conn.commit()
    return summary
