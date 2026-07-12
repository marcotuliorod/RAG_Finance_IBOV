import json
import uuid

from psycopg import Connection

from rag_b3.ingestion.cvm_rss.models import CvmFeedItem


def upsert_feed_item(conn: Connection, item: CvmFeedItem, job_run_id: uuid.UUID) -> bool:
    """Upsert por (feed_key, guid). Retorna True se o item era novo (INSERT),
    False se já existia (poll repetido só atualiza last_seen_at) — usado para
    contabilizar items_new vs items_duplicate no audit log do job."""
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into cvm_feed_item
                (feed_key, guid, link, title, summary, published_at, job_run_id, raw_entry)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (feed_key, guid) do update set
                last_seen_at = now()
            returning (xmax = 0) as inserted
            """,
            (
                item.feed_key,
                item.guid,
                item.link,
                item.title,
                item.summary,
                item.published_at,
                job_run_id,
                json.dumps(item.raw_entry, default=str),
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return bool(row[0])
