import json
import uuid
from typing import Any

from psycopg import Connection


class AuditLogger:
    """Grava em ingestion_audit_log (RF-10: trilha de auditoria imutável).

    A tabela é append-only por trigger de banco (rejeita UPDATE/DELETE) — este
    logger só faz INSERT, nunca tenta corrigir uma linha já gravada.
    """

    def log(
        self,
        conn: Connection,
        *,
        source: str,
        action: str,
        status: str,
        request_ref: str | None = None,
        http_status: int | None = None,
        error_code: str | None = None,
        raw_response: Any = None,
        job_run_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into ingestion_audit_log
                    (source, action, request_ref, status, http_status,
                     error_code, raw_response, job_run_id, metadata)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source,
                    action,
                    request_ref,
                    status,
                    http_status,
                    error_code,
                    json.dumps(raw_response) if raw_response is not None else None,
                    job_run_id,
                    json.dumps(metadata or {}),
                ),
            )
