import logging

import httpx
from psycopg import Connection
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from rag_b3.common.audit import AuditLogger
from rag_b3.common.job_run import JobRunTracker
from rag_b3.ingestion.cvm_rss.feeds import FEEDS
from rag_b3.ingestion.cvm_rss.parser import fetch_feed_content, parse_entries
from rag_b3.ingestion.cvm_rss.repository import upsert_feed_item

logger = logging.getLogger(__name__)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)),
)
def _fetch_with_retry(url: str) -> str:
    return fetch_feed_content(url)


def run_cvm_rss_ingestion(conn: Connection) -> dict:
    """Job RF-01 (ajustado): poll dos 6 feeds institucionais/regulatórios da
    CVM. Falha em um feed (fora do ar, XML malformado) não derruba os
    demais — cada feed é isolado e logado individualmente (RF-10)."""
    tracker = JobRunTracker()
    audit = AuditLogger()
    job_run_id = tracker.start(conn, "cvm_rss")
    conn.commit()

    summary: dict = {"feeds_ok": 0, "feeds_failed": 0, "items_new": 0, "items_duplicate": 0}

    for feed_key, url in FEEDS.items():
        try:
            content = _fetch_with_retry(url)
            items, bozo = parse_entries(feed_key, content)
        except Exception as exc:
            logger.warning("Falha ao buscar/parsear feed %s: %s", feed_key, exc)
            summary["feeds_failed"] += 1
            audit.log(
                conn,
                source="cvm_rss",
                action="poll_feed",
                request_ref=feed_key,
                status="error",
                job_run_id=job_run_id,
                metadata={"error": str(exc)},
            )
            conn.commit()
            continue

        items_new = 0
        for item in items:
            if upsert_feed_item(conn, item, job_run_id):
                items_new += 1
        items_duplicate = len(items) - items_new

        summary["feeds_ok"] += 1
        summary["items_new"] += items_new
        summary["items_duplicate"] += items_duplicate
        audit.log(
            conn,
            source="cvm_rss",
            action="poll_feed",
            request_ref=feed_key,
            status="success",
            job_run_id=job_run_id,
            metadata={
                "items_found": len(items),
                "items_new": items_new,
                "items_duplicate": items_duplicate,
                "bozo": bozo,
            },
        )
        conn.commit()

    status = "success" if summary["feeds_failed"] == 0 else (
        "partial_success" if summary["feeds_ok"] > 0 else "failed"
    )
    tracker.finish(conn, job_run_id, status, summary)
    conn.commit()
    return summary
