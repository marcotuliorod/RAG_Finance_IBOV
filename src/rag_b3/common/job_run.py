import json
import uuid

from psycopg import Connection


class JobRunTracker:
    """Abre/fecha linhas em ingestion_job_run — 1 por execução de job."""

    def start(self, conn: Connection, source: str) -> uuid.UUID:
        with conn.cursor() as cur:
            cur.execute(
                "insert into ingestion_job_run (source) values (%s) returning id",
                (source,),
            )
            row = cur.fetchone()
            assert row is not None
            return row[0]

    def finish(
        self,
        conn: Connection,
        job_run_id: uuid.UUID,
        status: str,
        summary: dict,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                update ingestion_job_run
                   set status = %s, summary = %s, finished_at = now()
                 where id = %s
                """,
                (status, json.dumps(summary), job_run_id),
            )
