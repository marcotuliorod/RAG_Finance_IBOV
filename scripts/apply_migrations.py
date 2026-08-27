#!/usr/bin/env python3
"""Aplica db/migrations/*.sql em ordem contra DATABASE_URL — substitui o
editor SQL do painel Supabase (não existe mais fora do Supabase).

Idempotente: uma tabela `schema_migrations` registra o nome de cada arquivo
já aplicado, e o script pula qualquer migração já registrada. Isso permite
rodar o script repetidamente contra o mesmo banco (ex.: toda vez que o
container `app` sobe, ou em todo run de CI contra um Postgres novo) sem
falhar em `CREATE TABLE`/constraint já existente — antes desta mudança
(docs/audit/TECHNICAL_AUDIT.md F-12), o script só funcionava em "banco
novo, aplica tudo uma vez"."""

import logging
import sys
from pathlib import Path

from psycopg import Connection

from rag_b3.common.db import get_connection
from rag_b3.common.logging_config import configure_logging
from rag_b3.config.settings import get_settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


def _ensure_migrations_table(conn: Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists schema_migrations (
                filename text primary key,
                applied_at timestamptz not null default now()
            )
            """
        )
    conn.commit()


def _applied_migrations(conn: Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("select filename from schema_migrations")
        return {row[0] for row in cur.fetchall()}


def main() -> int:
    configure_logging()
    settings = get_settings()

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.error("Nenhum arquivo .sql encontrado em %s", MIGRATIONS_DIR)
        return 1

    with get_connection(settings.database_url) as conn:
        _ensure_migrations_table(conn)
        already_applied = _applied_migrations(conn)

        newly_applied = 0
        for path in migration_files:
            if path.name in already_applied:
                logger.info("Já aplicada, pulando: %s", path.name)
                continue

            logger.info("Aplicando %s", path.name)
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "insert into schema_migrations (filename) values (%s)", (path.name,)
                )
            # Commit por arquivo: uma falha na próxima migração não deve
            # desfazer as que já foram aplicadas e registradas com sucesso.
            conn.commit()
            newly_applied += 1

    logger.info(
        "%d novas migrações aplicadas (%d já estavam aplicadas, %d no total)",
        newly_applied,
        len(already_applied),
        len(migration_files),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
